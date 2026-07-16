from __future__ import annotations

import html
import smtplib
import ssl
from datetime import datetime, time, timedelta, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import cfg, env, site_name, site_url
from app.models import EmailSubscriber, Job, SiteSetting, SubscriptionDigestRun

PKT = ZoneInfo("Asia/Karachi")
DEFAULT_DIGEST_SUBJECT = "Daily Job Alerts from {site_title} — {date}"
DEFAULT_DIGEST_BODY = (
    "Dear Sir/Madam,\n\n"
    "Here are the job postings published from {range_start} to {range_end}."
)


def _setting(db: Session, key: str, default: str) -> str:
    row = db.get(SiteSetting, key)
    return (row.value or default) if row else default


def digest_templates(db: Session) -> tuple[str, str]:
    return (
        _setting(db, "digest_subject_template", DEFAULT_DIGEST_SUBJECT),
        _setting(db, "digest_body_template", DEFAULT_DIGEST_BODY),
    )


def set_digest_templates(db: Session, *, subject_template: str, body_template: str) -> None:
    for key, value in (
        ("digest_subject_template", subject_template.strip()),
        ("digest_body_template", body_template.strip()),
    ):
        row = db.get(SiteSetting, key)
        if row:
            row.value = value
            row.updated_at = datetime.utcnow()
        else:
            db.add(SiteSetting(key=key, value=value, updated_at=datetime.utcnow()))


def digest_window(now: datetime | None = None) -> tuple[datetime, datetime, datetime, datetime]:
    current = now or datetime.now(PKT)
    if current.tzinfo is None:
        current = current.replace(tzinfo=PKT)
    else:
        current = current.astimezone(PKT)
    noon = datetime.combine(current.date(), time(hour=12), tzinfo=PKT)
    window_end_pkt = noon if current >= noon else noon - timedelta(days=1)
    window_start_pkt = window_end_pkt - timedelta(days=1)
    start_utc = window_start_pkt.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = window_end_pkt.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc, window_start_pkt, window_end_pkt


def _format_pkt(value: datetime) -> str:
    return value.strftime("%b %d, %Y at 12:00 PM PKT")


def _site_title(db: Session) -> str:
    row = db.get(SiteSetting, "site_title")
    return (row.value if row and row.value else None) or str(
        cfg("site", "title", default=site_name())
    )


def _render_text(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def build_digest_message(
    db: Session,
    subscriber: EmailSubscriber,
    jobs: list[Job],
    *,
    window_start_pkt: datetime,
    window_end_pkt: datetime,
) -> EmailMessage:
    title = _site_title(db)
    base_url = site_url().rstrip("/")
    subject_template, body_template = digest_templates(db)
    values = {
        "site_title": title,
        "date": window_end_pkt.strftime("%b %d, %Y"),
        "range_start": _format_pkt(window_start_pkt),
        "range_end": _format_pkt(window_end_pkt),
    }
    subject = _render_text(subject_template, values)
    body_intro = _render_text(body_template, values)

    plain_jobs: list[str] = []
    html_jobs: list[str] = []
    for job in jobs:
        url = f"{base_url}/jobs/{job.slug or job.id}"
        deadline = (
            job.deadline_date.strftime("%b %d, %Y") if job.deadline_date else "Not specified"
        )
        plain_jobs.append(f"- {job.title} — Deadline: {deadline}\n  {url}")
        html_jobs.append(
            "<li>"
            f'<a href="{html.escape(url, quote=True)}"><strong>{html.escape(job.title)}</strong></a>'
            f"<br>Deadline: {html.escape(deadline)}"
            "</li>"
        )

    unsubscribe_url = f"{base_url}/unsubscribe?token={subscriber.unsubscribe_token}"
    plain = (
        f"{title}\n\n{body_intro}\n\n"
        + "\n\n".join(plain_jobs)
        + f"\n\nRegards,\n{title}\n\nTo stop receiving these emails, unsubscribe here:\n{unsubscribe_url}"
    )
    intro_html = "<br>".join(html.escape(body_intro).splitlines())
    html_body = (
        f'<h2><a href="{html.escape(base_url, quote=True)}">{html.escape(title)}</a></h2>'
        f"<p>{intro_html}</p>"
        f"<ul>{''.join(html_jobs)}</ul>"
        f'<p>Regards,<br><a href="{html.escape(base_url, quote=True)}">{html.escape(title)}</a></p>'
        f'<p style="margin-top:28px;font-size:12px;color:#64748b">No longer want these alerts? '
        f'<a href="{html.escape(unsubscribe_url, quote=True)}">Unsubscribe from daily job alerts</a>.</p>'
    )

    from_email = env("SMTP_FROM_EMAIL") or env("SMTP_USERNAME")
    if not from_email:
        raise RuntimeError("SMTP_FROM_EMAIL or SMTP_USERNAME must be configured")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = subscriber.subscribed_email
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=from_email.rpartition("@")[2] or None)
    message.set_content(plain)
    message.add_alternative(html_body, subtype="html")
    return message


def _send_smtp_message(message: EmailMessage) -> None:
    host = env("SMTP_HOST")
    username = env("SMTP_USERNAME")
    password = env("SMTP_PASSWORD")
    if not host:
        raise RuntimeError("SMTP_HOST must be configured")
    if password and host.lower() == "smtp.gmail.com":
        password = "".join(password.split())
    port = int(env("SMTP_PORT", "587") or "587")
    timeout = int(env("SMTP_TIMEOUT_SECONDS", "15") or "15")
    use_ssl = (env("SMTP_USE_SSL", "false") or "false").lower() in {"1", "true", "yes"}
    starttls = (env("SMTP_STARTTLS", "true") or "true").lower() in {"1", "true", "yes"}
    authenticate = (env("SMTP_AUTH", "true") or "true").lower() in {"1", "true", "yes"}
    context = ssl.create_default_context()

    smtp_factory = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    kwargs = {"context": context} if use_ssl else {}
    with smtp_factory(host, port, timeout=timeout, **kwargs) as smtp:
        if not use_ssl:
            smtp.ehlo()
            if starttls:
                smtp.starttls(context=context)
                smtp.ehlo()
        if authenticate:
            if not username or not password:
                raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD must be configured")
            smtp.login(username, password)
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


def send_daily_digest(
    db: Session,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> dict[str, object]:
    start_utc, end_utc, start_pkt, end_pkt = digest_window(now)
    existing = db.execute(
        select(SubscriptionDigestRun).where(SubscriptionDigestRun.window_end == end_utc)
    ).scalar_one_or_none()
    if existing and existing.status in {"completed", "partial", "no_jobs", "no_subscribers"} and not force:
        return {
            "status": "already_processed",
            "window_start": start_utc,
            "window_end": end_utc,
            "jobs_count": existing.jobs_count,
            "recipients_count": existing.recipients_count,
            "sent_count": existing.sent_count,
            "failed_count": existing.failed_count,
            "message": "This daily digest window has already been processed.",
        }

    jobs = (
        db.execute(
            select(Job)
            .where(Job.published_date >= start_utc, Job.published_date < end_utc)
            .order_by(Job.published_date.asc(), Job.title.asc())
        )
        .scalars()
        .all()
    )
    subscribers = (
        db.execute(
            select(EmailSubscriber)
            .where(EmailSubscriber.is_active.is_(True))
            .order_by(EmailSubscriber.subscribed_at.asc())
        )
        .scalars()
        .all()
    )
    run = existing or SubscriptionDigestRun(
        id=__import__("uuid").uuid4().hex,
        window_start=start_utc,
        window_end=end_utc,
        created_at=datetime.utcnow(),
    )
    if not existing:
        db.add(run)
    run.window_start = start_utc
    run.status = "running"
    run.jobs_count = len(jobs)
    run.recipients_count = len(subscribers)
    run.sent_count = 0
    run.failed_count = 0
    run.error = None
    db.commit()

    if not jobs:
        run.status = "no_jobs"
        run.completed_at = datetime.utcnow()
        db.commit()
        status_message = "No new jobs were published in this window; no email was sent."
    elif not subscribers:
        run.status = "no_subscribers"
        run.completed_at = datetime.utcnow()
        db.commit()
        status_message = "There are no active subscribers; no email was sent."
    else:
        errors: list[str] = []
        for subscriber in subscribers:
            try:
                message = build_digest_message(
                    db,
                    subscriber,
                    jobs,
                    window_start_pkt=start_pkt,
                    window_end_pkt=end_pkt,
                )
                _send_smtp_message(message)
                subscriber.last_digest_sent_at = datetime.utcnow()
                subscriber.updated_at = datetime.utcnow()
                run.sent_count += 1
            except Exception as exc:
                run.failed_count += 1
                errors.append(f"{subscriber.user_uuid}: {type(exc).__name__}")
        run.status = "completed" if run.failed_count == 0 else "partial" if run.sent_count else "failed"
        run.error = "; ".join(errors[:20]) or None
        run.completed_at = datetime.utcnow()
        db.commit()
        status_message = f"Sent {run.sent_count} of {run.recipients_count} daily job alert emails."

    return {
        "status": run.status,
        "window_start": start_utc,
        "window_end": end_utc,
        "jobs_count": run.jobs_count,
        "recipients_count": run.recipients_count,
        "sent_count": run.sent_count,
        "failed_count": run.failed_count,
        "message": status_message,
    }


def subscriber_counts(db: Session) -> tuple[int, int]:
    total = db.execute(select(func.count()).select_from(EmailSubscriber)).scalar() or 0
    active = db.execute(
        select(func.count()).select_from(EmailSubscriber).where(EmailSubscriber.is_active.is_(True))
    ).scalar() or 0
    return int(total), int(active)
