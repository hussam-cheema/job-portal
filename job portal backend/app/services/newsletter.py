from __future__ import annotations

import html
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.config import canonical_site_url, cfg, env, site_name
from app.logging_config import get_logger
from app.models import (
    EmailSubscriber,
    Job,
    SiteSetting,
    SubscriptionDigestRun,
    SubscriptionEmailDelivery,
)
from app.services.smtp_transport import address_fingerprint, deliver_email_message

logger = get_logger("jobportal.newsletter")

# The existing setting keys are intentionally retained so production keeps any
# administrator-edited template after this event-driven migration.
LEGACY_DIGEST_SUBJECT = "Daily Job Alerts from {site_title} — {date}"
LEGACY_DIGEST_BODY = (
    "Dear Sir/Madam,\n\n"
    "Here are the job postings published from {range_start} to {range_end}."
)
DEFAULT_ALERT_SUBJECT = "New Job Alert: {job_title} — {site_title}"
DEFAULT_ALERT_BODY = "Dear Sir/Madam,\n\nA new job has been published on {site_title}."


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


def set_digest_templates(
    db: Session, *, subject_template: str, body_template: str
) -> None:
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
    *,
    rendering_context: tuple[str, str, str] | None = None,
) -> EmailMessage:
    if rendering_context is None:
        title = _site_title(db)
        subject_template, body_template = digest_templates(db)
    else:
        title, subject_template, body_template = rendering_context
    base_url = canonical_site_url()
    job_url = f"{base_url}/jobs/{job.slug or job.id}"
    published = (job.published_date or job.created_at or datetime.utcnow()).strftime(
        "%b %d, %Y"
    )
    deadline = (
        job.deadline_date.strftime("%b %d, %Y")
        if job.deadline_date
        else "Not specified"
    )
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
    public_api_url = (env("PUBLIC_API_URL") or base_url).rstrip("/")
    one_click_unsubscribe_url = (
        f"{public_api_url}/api/subscriptions/unsubscribe"
        f"?token={subscriber.unsubscribe_token}"
    )

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

    from_email = (
        env("EMAIL_FROM_EMAIL") or env("SMTP_FROM_EMAIL") or env("SMTP_USERNAME")
    )
    if not from_email:
        raise RuntimeError(
            "EMAIL_FROM_EMAIL, SMTP_FROM_EMAIL, or SMTP_USERNAME must be configured"
        )
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((title, from_email))
    message["To"] = subscriber.subscribed_email
    message["Reply-To"] = from_email
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=from_email.rpartition("@")[2] or None)
    message["List-Unsubscribe"] = f"<{one_click_unsubscribe_url}>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    site_domain = urlsplit(base_url).hostname or "pakistanjobsmarket.com"
    message["List-ID"] = f"{title} Job Alerts <job-alerts.{site_domain}>"
    message["Auto-Submitted"] = "auto-generated"
    message["X-Entity-Ref-ID"] = str(job.id)
    message.set_content(plain)
    message.add_alternative(html_body, subtype="html")
    return message


def _alert_rendering_context(db: Session) -> tuple[str, str, str]:
    """Load all shared email-template settings once for a delivery batch."""
    keys = {
        "site_title",
        "digest_subject_template",
        "digest_body_template",
    }
    settings = {
        key: value
        for key, value in db.execute(
            select(SiteSetting.key, SiteSetting.value).where(SiteSetting.key.in_(keys))
        ).all()
    }
    title = settings.get("site_title") or str(cfg("site", "title", default=site_name()))
    subject = settings.get("digest_subject_template") or DEFAULT_ALERT_SUBJECT
    body = settings.get("digest_body_template") or DEFAULT_ALERT_BODY
    if subject.strip() == LEGACY_DIGEST_SUBJECT:
        subject = DEFAULT_ALERT_SUBJECT
    if body.strip() == LEGACY_DIGEST_BODY:
        body = DEFAULT_ALERT_BODY
    return title, subject, body


def _send_smtp_message(message: EmailMessage):
    # Retain the historical function name for stable tests and retry hooks.
    return deliver_email_message(message)


def _deliver_with_retries(message: EmailMessage):
    attempts = max(1, min(5, int(env("SMTP_SEND_ATTEMPTS", "3") or "3")))
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return _send_smtp_message(message)
        except Exception as exc:
            last_error = exc
            # Configuration errors and Railway's plan-level SMTP restriction do
            # not improve with retries. Surface them immediately to the admin.
            if isinstance(exc, RuntimeError):
                break
            if attempt >= attempts:
                break
            delay = min(2.0, 0.35 * (2 ** (attempt - 1)))
            logger.warning(
                "new job SMTP attempt failed attempt=%s/%s retry_in=%.2fs error=%s",
                attempt,
                attempts,
                delay,
                type(exc).__name__,
            )
            time.sleep(delay)
    assert last_error is not None
    raise last_error


def _max_delivery_attempts() -> int:
    return max(
        1,
        min(20, int(env("NEWSLETTER_MAX_DELIVERY_ATTEMPTS", "5") or "5")),
    )


def _next_retry_at(attempts: int) -> datetime:
    delay_seconds = min(3600, 60 * (5 ** max(0, attempts - 1)))
    return datetime.utcnow() + timedelta(seconds=delay_seconds)


def _refresh_run_summary(db: Session, run_id: str) -> SubscriptionDigestRun | None:
    run = db.get(SubscriptionDigestRun, run_id)
    if not run:
        return None
    deliveries = db.execute(
        select(
            SubscriptionEmailDelivery.status,
            SubscriptionEmailDelivery.subscriber_id,
            SubscriptionEmailDelivery.last_error,
        ).where(SubscriptionEmailDelivery.run_id == run_id)
    ).all()
    run.recipients_count = len(deliveries)
    run.sent_count = sum(item.status == "delivered" for item in deliveries)
    run.failed_count = len(deliveries) - run.sent_count
    retrying = any(
        item.status in {"pending", "processing", "retrying"} for item in deliveries
    )
    if not deliveries:
        run.status = "no_subscribers"
    elif run.sent_count == len(deliveries):
        run.status = "completed"
    elif retrying:
        run.status = "retrying"
    elif run.sent_count:
        run.status = "partial"
    else:
        run.status = "failed"
    errors = [
        f"{item.subscriber_id}: {item.last_error}"
        for item in deliveries
        if item.status != "delivered" and item.last_error
    ]
    run.error = "; ".join(errors[:20]) or None
    run.completed_at = (
        datetime.utcnow()
        if run.status in {"completed", "partial", "failed", "no_subscribers"}
        else None
    )
    return run


def _run_result(run: SubscriptionDigestRun) -> dict[str, object]:
    return {
        "status": run.status,
        "jobs_count": 1,
        "recipients_count": run.recipients_count,
        "sent_count": run.sent_count,
        "failed_count": run.failed_count,
        "message": (
            f"Delivered {run.sent_count} of {run.recipients_count} new-job alerts."
            if run.status != "retrying"
            else (
                f"Delivered {run.sent_count} of {run.recipients_count} alerts; "
                f"{run.failed_count} recipient(s) are queued for automatic retry."
            )
        ),
    }


def process_pending_job_alerts(
    db: Session,
    *,
    job_id: str | None = None,
    max_deliveries: int = 100,
) -> dict[str, object]:
    """Claim and deliver queued subscriber alerts.

    Each recipient has a durable row, so a failed address does not interrupt
    other subscribers and pending work survives a container restart.
    """
    now = datetime.utcnow()
    stale_before = now - timedelta(minutes=10)
    db.execute(
        update(SubscriptionEmailDelivery)
        .where(
            SubscriptionEmailDelivery.status == "processing",
            SubscriptionEmailDelivery.last_attempt_at < stale_before,
        )
        .values(status="retrying", next_attempt_at=now, updated_at=now)
    )
    due = select(SubscriptionEmailDelivery.id).where(
        SubscriptionEmailDelivery.status.in_(["pending", "retrying"]),
        SubscriptionEmailDelivery.next_attempt_at <= now,
    )
    if job_id:
        due = due.where(SubscriptionEmailDelivery.job_id == job_id)
    candidate_ids = (
        due.order_by(SubscriptionEmailDelivery.created_at.asc())
        .limit(max(1, min(1000, max_deliveries)))
        .scalar_subquery()
    )
    claimed_at = datetime.utcnow()
    delivery_ids = list(
        db.execute(
            update(SubscriptionEmailDelivery)
            .where(
                SubscriptionEmailDelivery.id.in_(candidate_ids),
                SubscriptionEmailDelivery.status.in_(["pending", "retrying"]),
            )
            .values(
                status="processing",
                attempts=SubscriptionEmailDelivery.attempts + 1,
                last_attempt_at=claimed_at,
                updated_at=claimed_at,
            )
            .returning(SubscriptionEmailDelivery.id)
        ).scalars()
    )
    db.commit()

    touched_runs: set[str] = set()
    delivered_count = 0
    claimed_rows = db.execute(
        select(SubscriptionEmailDelivery, Job, EmailSubscriber)
        .outerjoin(Job, Job.id == SubscriptionEmailDelivery.job_id)
        .outerjoin(
            EmailSubscriber,
            EmailSubscriber.user_uuid == SubscriptionEmailDelivery.subscriber_id,
        )
        .where(SubscriptionEmailDelivery.id.in_(delivery_ids))
    ).all()
    deliveries_by_id = {
        delivery.id: (delivery, job, subscriber)
        for delivery, job, subscriber in claimed_rows
    }
    rendering_context = _alert_rendering_context(db) if delivery_ids else None
    previous_expire_on_commit = db.expire_on_commit
    db.expire_on_commit = False
    for delivery_id in delivery_ids:
        loaded = deliveries_by_id.get(delivery_id)
        if loaded is None:
            continue
        delivery, job, subscriber = loaded
        touched_runs.add(delivery.run_id)
        if not job or not subscriber or not subscriber.is_active:
            delivery.status = "cancelled"
            delivery.last_error = "Job or active subscriber no longer exists"
            delivery.updated_at = datetime.utcnow()
            db.commit()
            continue

        try:
            message = build_job_alert_message(
                db,
                subscriber,
                job,
                rendering_context=rendering_context,
            )
            receipt = _deliver_with_retries(message)
            delivered_at = datetime.utcnow()
            delivery.status = "delivered"
            delivery.last_error = None
            delivery.smtp_message_id = str(
                getattr(receipt, "message_id", message.get("Message-ID", ""))
            )
            delivery.delivered_at = delivered_at
            delivery.updated_at = delivered_at
            subscriber.last_digest_sent_at = delivered_at
            subscriber.updated_at = delivered_at
            delivered_count += 1
            logger.info(
                "new job alert accepted job_id=%s subscriber=%s message_id=%s "
                "smtp_code=%s smtp_response=%s",
                job.id,
                address_fingerprint(subscriber.subscribed_email),
                delivery.smtp_message_id,
                getattr(receipt, "response_code", "mocked"),
                getattr(receipt, "response", "mocked"),
            )
        except Exception as exc:
            detail = str(exc).strip()
            delivery.last_error = (
                f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__
            )[:500]
            delivery.updated_at = datetime.utcnow()
            if delivery.attempts >= _max_delivery_attempts():
                delivery.status = "failed"
            else:
                delivery.status = "retrying"
                delivery.next_attempt_at = _next_retry_at(delivery.attempts)
            logger.exception(
                "new job alert failed job_id=%s subscriber_id=%s queued_for_retry=%s",
                delivery.job_id,
                delivery.subscriber_id,
                delivery.status == "retrying",
            )
        db.commit()

    db.expire_on_commit = previous_expire_on_commit

    for run_id in touched_runs:
        _refresh_run_summary(db, run_id)
    db.commit()

    return {
        "processed_count": len(touched_runs) and len(delivery_ids) or 0,
        "delivered_count": delivered_count,
    }


def queue_new_job_alert(
    db: Session,
    job: Job,
    *,
    force_resend: bool = False,
) -> SubscriptionDigestRun:
    """Stage one durable delivery per active subscriber in the current transaction.

    The caller that publishes a job uses this before committing, so the job and
    its complete subscriber outbox either persist together or both roll back.
    SMTP is intentionally not contacted while that database transaction is open.
    """
    existing = db.execute(
        select(SubscriptionDigestRun).where(SubscriptionDigestRun.job_id == job.id)
    ).scalar_one_or_none()
    if existing and not force_resend:
        return existing
    if existing:
        db.execute(
            delete(SubscriptionEmailDelivery).where(
                SubscriptionEmailDelivery.run_id == existing.id
            )
        )
        db.delete(existing)
        db.flush()

    subscriber_ids = (
        db.execute(
            select(EmailSubscriber.user_uuid)
            .where(EmailSubscriber.is_active.is_(True))
            .order_by(EmailSubscriber.subscribed_at.asc())
        )
        .scalars()
        .all()
    )
    now = datetime.utcnow()
    run = SubscriptionDigestRun(
        id=uuid4().hex,
        job_id=job.id,
        window_start=job.created_at or now,
        window_end=now,
        status="running",
        jobs_count=1,
        recipients_count=len(subscriber_ids),
        sent_count=0,
        failed_count=0,
        created_at=now,
    )
    db.add(run)
    db.flush()

    if not subscriber_ids:
        run.status = "no_subscribers"
        run.completed_at = now
        return run

    for subscriber_id in subscriber_ids:
        db.add(
            SubscriptionEmailDelivery(
                id=uuid4().hex,
                run_id=run.id,
                job_id=job.id,
                subscriber_id=subscriber_id,
                status="pending",
                attempts=0,
                next_attempt_at=now,
                created_at=now,
                updated_at=now,
            )
        )
    db.flush()
    return run


def send_new_job_alert(
    db: Session,
    job: Job,
    *,
    force_resend: bool = False,
) -> dict[str, object]:
    """Queue and immediately attempt one committed job for every subscriber.

    This remains the entry point for manual resend/recovery. The normal publish
    route stages the same outbox inside the job transaction, then calls the
    processor immediately after that atomic commit.
    """
    run = queue_new_job_alert(db, job, force_resend=force_resend)
    db.commit()
    if run.recipients_count:
        process_pending_job_alerts(
            db,
            job_id=job.id,
            max_deliveries=run.recipients_count,
        )
    db.refresh(run)
    return _run_result(run)


def subscriber_counts(db: Session) -> tuple[int, int]:
    total = db.execute(select(func.count()).select_from(EmailSubscriber)).scalar() or 0
    active = (
        db.execute(
            select(func.count())
            .select_from(EmailSubscriber)
            .where(EmailSubscriber.is_active.is_(True))
        ).scalar()
        or 0
    )
    return int(total), int(active)
