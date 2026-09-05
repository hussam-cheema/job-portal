from __future__ import annotations

import secrets
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.database import get_db
from app.models import (
    EmailSubscriber,
    Job,
    SubscriberApiAccess,
    SubscriptionDigestRun,
    User,
)
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
    api_access = db.execute(
        select(SubscriberApiAccess).where(
            SubscriberApiAccess.subscriber_email == email
        )
    ).scalar_one_or_none()
    if api_access:
        api_access.subscriber_id = row.user_uuid
        api_access.subscriber_is_active = True
        api_access.updated_at = datetime.utcnow()
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
    api_access = db.execute(
        select(SubscriberApiAccess).where(
            SubscriberApiAccess.subscriber_email == row.subscribed_email
        )
    ).scalar_one_or_none()
    if api_access:
        api_access.subscriber_is_active = False
        api_access.is_key_active = False
        api_access.updated_at = datetime.utcnow()
    db.delete(row)
    db.commit()
    return SubscriptionResult(
        status="unsubscribed", message="You have been unsubscribed."
    )


@router.get("/admin/subscriptions", response_model=DigestAdminSummary)
def admin_summary(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    total, active = subscriber_counts(db)
    subject, body = digest_templates(db)
    last_row = db.execute(
        select(SubscriptionDigestRun, Job.title)
        .outerjoin(Job, Job.id == SubscriptionDigestRun.job_id)
        .order_by(SubscriptionDigestRun.window_end.desc())
        .limit(1)
    ).first()
    last = last_row[0] if last_row else None
    last_job_title = last_row[1] if last_row else None
    provider, delivery_ready, delivery_message = email_delivery_status()
    api_rows = db.execute(
        select(SubscriberApiAccess).order_by(SubscriberApiAccess.updated_at.desc())
    ).scalars().all()
    now = datetime.utcnow()
    return DigestAdminSummary(
        subscriber_count=total,
        active_subscriber_count=active,
        subject_template=subject,
        body_template=body,
        last_digest_at=last.completed_at if last else None,
        last_digest_status=last.status if last else None,
        last_digest_job_id=last.job_id if last else None,
        last_digest_job_title=last_job_title,
        last_digest_recipients_count=last.recipients_count if last else 0,
        last_digest_sent_count=last.sent_count if last else 0,
        last_digest_failed_count=last.failed_count if last else 0,
        last_digest_error=last.error if last else None,
        delivery_provider=provider,
        delivery_ready=delivery_ready,
        delivery_configuration_message=delivery_message,
        student_api_access=[
            {
                "subscriber_email": item.subscriber_email,
                "subscriber_is_active": item.subscriber_is_active,
                "key_prefix": item.api_key_prefix,
                "is_key_active": item.is_key_active,
                "quota_total": item.quota_total,
                "requests_used": item.requests_used,
                "requests_remaining": max(0, item.quota_total - item.requests_used),
                "verification_pending": bool(
                    item.verification_code_hash
                    and item.verification_expires_at
                    and item.verification_expires_at >= now
                ),
                "verification_expires_at": item.verification_expires_at,
                "verified_at": item.verified_at,
                "api_key_created_at": item.api_key_created_at,
                "api_key_last_used_at": item.api_key_last_used_at,
            }
            for item in api_rows
        ],
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
    latest = (
        db.execute(
            select(Job).order_by(Job.created_at.desc(), Job.published_date.desc())
        )
        .scalars()
        .first()
    )
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
