from __future__ import annotations

import secrets
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.database import get_db
from app.models import EmailSubscriber, Job, SubscriptionDigestRun, User
from app.schemas import (
    DigestAdminSummary,
    DigestTemplateUpdate,
    SubscriptionIn,
    SubscriptionResult,
)
from app.services.contact_security import validate_email
from app.services.newsletter import (
    digest_templates,
    send_new_job_alert,
    set_digest_templates,
    subscriber_counts,
)
from app.services.smtp_transport import email_delivery_status

router = APIRouter()


@router.post("/subscriptions", response_model=SubscriptionResult)
def subscribe(payload: SubscriptionIn, db: Session = Depends(get_db)):
    email = validate_email(payload.email)
    row = db.execute(
        select(EmailSubscriber).where(EmailSubscriber.subscribed_email == email)
    ).scalar_one_or_none()
    if row and row.is_active:
        return SubscriptionResult(
            status="already_subscribed",
            message="This email is already subscribed to new job alerts.",
        )
    if row:
        row.is_active = True
        row.subscribed_at = datetime.utcnow()
        row.unsubscribed_at = None
        row.unsubscribe_token = secrets.token_urlsafe(32)
        row.updated_at = datetime.utcnow()
    else:
        row = EmailSubscriber(
            user_uuid=str(uuid4()),
            subscribed_email=email,
            unsubscribe_token=secrets.token_urlsafe(32),
            is_active=True,
            subscribed_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
    db.commit()
    return SubscriptionResult(
        status="subscribed",
        message="Your email has been subscribed to new job alerts.",
    )


@router.post("/subscriptions/unsubscribe", response_model=SubscriptionResult)
def unsubscribe(token: str, db: Session = Depends(get_db)):
    row = db.execute(
        select(EmailSubscriber).where(EmailSubscriber.unsubscribe_token == token)
    ).scalar_one_or_none()
    if not row or not row.is_active:
        return SubscriptionResult(
            status="not_subscribed",
            message="This subscription is already inactive or the link is invalid.",
        )
    # An unsubscribe is a deletion request, not a soft-disable. Removing the
    # row keeps dashboard counts accurate and avoids retaining an address that
    # explicitly asked to leave the mailing list.
    db.delete(row)
    db.commit()
    return SubscriptionResult(status="unsubscribed", message="You have been unsubscribed.")


@router.get("/admin/subscriptions", response_model=DigestAdminSummary)
def admin_summary(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    total, active = subscriber_counts(db)
    subject, body = digest_templates(db)
    last = db.execute(
        select(SubscriptionDigestRun).order_by(SubscriptionDigestRun.window_end.desc())
    ).scalars().first()
    last_job = db.get(Job, last.job_id) if last and last.job_id else None
    provider, delivery_ready, delivery_message = email_delivery_status()
    return DigestAdminSummary(
        subscriber_count=total,
        active_subscriber_count=active,
        subject_template=subject,
        body_template=body,
        last_digest_at=last.completed_at if last else None,
        last_digest_status=last.status if last else None,
        last_digest_job_id=last.job_id if last else None,
        last_digest_job_title=last_job.title if last_job else None,
        last_digest_recipients_count=last.recipients_count if last else 0,
        last_digest_sent_count=last.sent_count if last else 0,
        last_digest_failed_count=last.failed_count if last else 0,
        last_digest_error=last.error if last else None,
        delivery_provider=provider,
        delivery_ready=delivery_ready,
        delivery_configuration_message=delivery_message,
    )


@router.put("/admin/subscriptions/template", response_model=DigestAdminSummary)
def update_template(
    payload: DigestTemplateUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    set_digest_templates(
        db,
        subject_template=payload.subject_template,
        body_template=payload.body_template,
    )
    db.commit()
    return admin_summary(db, _)


@router.post("/admin/subscriptions/resend-latest")
def resend_latest_job_alert(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    _provider, delivery_ready, delivery_message = email_delivery_status()
    if not delivery_ready:
        return {
            "status": "configuration_required",
            "sent_count": 0,
            "failed_count": 0,
            "message": delivery_message,
        }
    latest = db.execute(
        select(Job).order_by(Job.created_at.desc(), Job.published_date.desc())
    ).scalars().first()
    if not latest:
        return {
            "status": "no_jobs",
            "sent_count": 0,
            "failed_count": 0,
            "message": "No job post is available to resend.",
        }
    result = send_new_job_alert(db, latest, force_resend=True)
    return {
        **result,
        "job_id": latest.id,
        "job_title": latest.title,
    }
