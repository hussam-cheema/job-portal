from __future__ import annotations

import html
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import cfg, env, site_name, site_url
from app.logging_config import get_logger
from app.models import EmailSubscriber, Job, SiteSetting, SubscriptionDigestRun

logger = get_logger("jobportal.newsletter")

# The existing setting keys are intentionally retained so production keeps any
# administrator-edited template after this event-driven migration.
LEGACY_DIGEST_SUBJECT = "Daily Job Alerts from {site_title} — {date}"
LEGACY_DIGEST_BODY = (
    "Dear Sir/Madam,\n\n"
    "Here are the job postings published from {range_start} to {range_end}."
)
DEFAULT_ALERT_SUBJECT = "New Job Alert: {job_title} — {site_title}"
DEFAULT_ALERT_BODY = (
    "Dear Sir/Madam,\n\n"
    "A new job has been published on {site_title}."
)


def _setting(db: Session, key: str, default: str) -> str:
    row = db.get(SiteSetting, key)
    return (row.value or default) if row else default


def digest_templates(db: Session) -> tuple[str, str]:
    """Return the new-job alert templates, upgrading untouched legacy defaults."""
    subject = _setting(db, "digest_subject_template", DEFAULT_ALERT_SUBJECT)
    body = _setting(db, "digest_body_template", DEFAULT_ALERT_BODY)
    if subject.strip() == LEGACY_DIGEST_SUBJECT:
        subject = DEFAULT_ALERT_SUBJECT
    if body.strip() == LEGACY_DIGEST_BODY:
        body = DEFAULT_ALERT_BODY
    return subject, body


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


def build_job_alert_message(
    db: Session,
    subscriber: EmailSubscriber,
    job: Job,
) -> EmailMessage:
    title = _site_title(db)
    base_url = site_url().rstrip("/")
    job_url = f"{base_url}/jobs/{job.slug or job.id}"
    published = (job.published_date or job.created_at or datetime.utcnow()).strftime(
        "%b %d, %Y"
    )
    deadline = (
        job.deadline_date.strftime("%b %d, %Y")
        if job.deadline_date
        else "Not specified"
    )
    subject_template, body_template = digest_templates(db)
    values = {
        "site_title": title,
        "date": published,
        "job_title": job.title,
        "job_url": job_url,
        "deadline": deadline,
        "published_date": published,
        # Old administrator templates continue rendering sensibly instead of
        # exposing unresolved noon-window placeholders.
        "range_start": published,
        "range_end": published,
    }
    subject = _render_text(subject_template, values)
    body_intro = _render_text(body_template, values)
    unsubscribe_url = f"{base_url}/unsubscribe?token={subscriber.unsubscribe_token}"

    plain = (
        f"{title}\n\n{body_intro}\n\n"
        f"{job.title}\n{job_url}\nDeadline: {deadline}\n\n"
        f"Regards,\n{title}\n\n"
        "To stop receiving these emails, unsubscribe here:\n"
        f"{unsubscribe_url}"
    )
    intro_html = "<br>".join(html.escape(body_intro).splitlines())
    html_body = (
        f'<h2><a href="{html.escape(base_url, quote=True)}">{html.escape(title)}</a></h2>'
        f"<p>{intro_html}</p>"
        f'<p><a href="{html.escape(job_url, quote=True)}"><strong>{html.escape(job.title)}</strong></a>'
        f"<br>Deadline: {html.escape(deadline)}</p>"
        f'<p>Regards,<br><a href="{html.escape(base_url, quote=True)}">{html.escape(title)}</a></p>'
        f'<p style="margin-top:28px;font-size:12px;color:#64748b">No longer want these alerts? '
        f'<a href="{html.escape(unsubscribe_url, quote=True)}">Unsubscribe from job alerts</a>.</p>'
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


def send_new_job_alert(db: Session, job: Job) -> dict[str, object]:
    """Send one committed job to active subscribers exactly once.

    Delivery errors are recorded and returned; they are deliberately not raised
    so an SMTP outage can never roll back or hide an otherwise valid job post.
    """
    existing = db.execute(
        select(SubscriptionDigestRun).where(SubscriptionDigestRun.job_id == job.id)
    ).scalar_one_or_none()
    if existing:
        return {
            "status": "already_processed",
            "jobs_count": 1,
            "recipients_count": existing.recipients_count,
            "sent_count": existing.sent_count,
            "failed_count": existing.failed_count,
            "message": "This job alert has already been processed.",
        }

    subscribers = (
        db.execute(
            select(EmailSubscriber)
            .where(EmailSubscriber.is_active.is_(True))
            .order_by(EmailSubscriber.subscribed_at.asc())
        )
        .scalars()
        .all()
    )
    now = datetime.utcnow()
    run = SubscriptionDigestRun(
        id=__import__("uuid").uuid4().hex,
        job_id=job.id,
        window_start=job.created_at or now,
        window_end=now,
        status="running",
        jobs_count=1,
        recipients_count=len(subscribers),
        sent_count=0,
        failed_count=0,
        created_at=now,
    )
    db.add(run)

    if not subscribers:
        run.status = "no_subscribers"
        run.completed_at = datetime.utcnow()
        db.commit()
        return {
            "status": run.status,
            "jobs_count": 1,
            "recipients_count": 0,
            "sent_count": 0,
            "failed_count": 0,
            "message": "There are no active subscribers; no email was sent.",
        }

    errors: list[str] = []
    for subscriber in subscribers:
        try:
            message = build_job_alert_message(db, subscriber, job)
            _send_smtp_message(message)
            subscriber.last_digest_sent_at = datetime.utcnow()
            subscriber.updated_at = datetime.utcnow()
            run.sent_count += 1
        except Exception as exc:
            run.failed_count += 1
            errors.append(f"{subscriber.user_uuid}: {type(exc).__name__}")
            logger.exception(
                "new job alert failed job_id=%s subscriber_id=%s",
                job.id,
                subscriber.user_uuid,
            )
    run.status = "completed" if run.failed_count == 0 else "partial" if run.sent_count else "failed"
    run.error = "; ".join(errors[:20]) or None
    run.completed_at = datetime.utcnow()
    db.commit()
    return {
        "status": run.status,
        "jobs_count": 1,
        "recipients_count": run.recipients_count,
        "sent_count": run.sent_count,
        "failed_count": run.failed_count,
        "message": f"Sent {run.sent_count} of {run.recipients_count} new-job alert emails.",
    }


def subscriber_counts(db: Session) -> tuple[int, int]:
    total = db.execute(select(func.count()).select_from(EmailSubscriber)).scalar() or 0
    active = db.execute(
        select(func.count())
        .select_from(EmailSubscriber)
        .where(EmailSubscriber.is_active.is_(True))
    ).scalar() or 0
    return int(total), int(active)
