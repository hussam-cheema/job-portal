from __future__ import annotations

import hashlib
import hmac
import html
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Iterable
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.config import canonical_site_url, env, jwt_secret
from app.database import get_db
from app.logging_config import get_logger
from app.models import (
    EmailSubscriber,
    StudentApiSecurityEvent,
    SubscriberApiAccess,
)
from app.services.contact_security import client_ip, validate_email
from app.services.smtp_transport import deliver_email_message, email_delivery_status

logger = get_logger("jobportal.student_api")

API_QUOTA = 50
CODE_TTL_SECONDS = 10 * 60
CODE_RESEND_COOLDOWN_SECONDS = 60
MAX_CODE_ATTEMPTS = 5
API_KEY_PREFIX = "pjm_live_"

# A fast in-process sliding window rejects bursts before they can create DB
# load. Matching persistent counters below keep the protection effective after
# restarts and make it work consistently across replicas.
_burst_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_burst_lock = threading.Lock()


def _secret() -> bytes:
    configured = env("STUDENT_API_SECRET")
    return (configured or jwt_secret()).encode("utf-8")


def secure_digest(namespace: str, value: str) -> str:
    return hmac.new(
        _secret(),
        f"{namespace}:{value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _scope_hash(scope_type: str, value: str) -> str:
    return secure_digest(f"rate:{scope_type}", value)


def _memory_limit(scope_hash: str, event_type: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    key = (scope_hash, event_type)
    with _burst_lock:
        hits = _burst_hits[key]
        cutoff = now - window_seconds
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait before trying again.",
                headers={"Retry-After": str(window_seconds)},
            )
        hits.append(now)


def enforce_security_limits(
    db: Session,
    checks: Iterable[tuple[str, str, int, int]],
) -> None:
    """Apply matching memory and persistent fixed-window abuse limits."""
    now = datetime.utcnow()
    prepared = list(checks)
    for scope_hash, event_type, limit, window_seconds in prepared:
        _memory_limit(scope_hash, event_type, limit, window_seconds)
        count = db.execute(
            select(func.count())
            .select_from(StudentApiSecurityEvent)
            .where(
                StudentApiSecurityEvent.scope_hash == scope_hash,
                StudentApiSecurityEvent.event_type == event_type,
                StudentApiSecurityEvent.occurred_at
                >= now - timedelta(seconds=window_seconds),
            )
        ).scalar() or 0
        if count >= limit:
            db.add(
                StudentApiSecurityEvent(
                    id=str(uuid4()),
                    scope_hash=scope_hash,
                    event_type=event_type,
                    allowed=False,
                    occurred_at=now,
                )
            )
            db.commit()
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait before trying again.",
                headers={"Retry-After": str(window_seconds)},
            )
    for scope_hash, event_type, _limit, _window_seconds in prepared:
        db.add(
            StudentApiSecurityEvent(
                id=str(uuid4()),
                scope_hash=scope_hash,
                event_type=event_type,
                allowed=True,
                occurred_at=now,
            )
        )


def _verification_message(email: str, code: str) -> EmailMessage:
    from_email = env("EMAIL_FROM_EMAIL") or env("SMTP_FROM_EMAIL") or env("SMTP_USERNAME")
    if not from_email:
        raise RuntimeError("Email delivery sender is not configured")
    title = "Pakistan Jobs Market"
    docs_url = f"{canonical_site_url()}/tools/api"
    plain = (
        f"Your {title} student API verification code is: {code}\n\n"
        f"It expires in 10 minutes and can be used once.\n\n"
        f"Return to {docs_url} to verify your email. If you did not request this "
        "code, you can ignore this message."
    )
    rich = (
        f"<h2>{html.escape(title)} student API</h2>"
        "<p>Use this one-time verification code:</p>"
        f'<p style="font-size:28px;font-weight:700;letter-spacing:6px">{code}</p>'
        "<p>The code expires in 10 minutes. If you did not request it, you can "
        "ignore this message.</p>"
        f'<p><a href="{html.escape(docs_url, quote=True)}">Return to the API tool</a></p>'
    )
    message = EmailMessage()
    message["Subject"] = f"Your {title} API verification code"
    message["From"] = formataddr((title, from_email))
    message["To"] = email
    message["Reply-To"] = from_email
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=from_email.rpartition("@")[2] or None)
    site_domain = urlsplit(canonical_site_url()).hostname or "pakistanjobsmarket.com"
    message["List-ID"] = f"{title} Student API <student-api.{site_domain}>"
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(plain)
    message.add_alternative(rich, subtype="html")
    return message


def request_verification_code(db: Session, request: Request, raw_email: str) -> dict:
    email = validate_email(raw_email)
    now = datetime.utcnow()
    purge_old_security_events(db)
    ip_hash = _scope_hash("ip", client_ip(request))
    email_hash = _scope_hash("email", email)
    enforce_security_limits(
        db,
        (
            (ip_hash, "code_request_ip", 8, 3600),
            (email_hash, "code_request_email", 3, 3600),
            (_scope_hash("global", "verification"), "code_request_global", 250, 3600),
        ),
    )

    subscriber = db.execute(
        select(EmailSubscriber).where(EmailSubscriber.subscribed_email == email)
    ).scalar_one_or_none()
    access = db.execute(
        select(SubscriberApiAccess).where(SubscriberApiAccess.subscriber_email == email)
    ).scalar_one_or_none()
    if not subscriber or not subscriber.is_active:
        if access:
            access.subscriber_is_active = False
            access.is_key_active = False
            access.updated_at = now
        db.commit()
        return {
            "status": "subscription_required",
            "message": "You need to subscribe to the newsletter before requesting an API key.",
        }

    if access and access.last_code_sent_at:
        elapsed = int((now - access.last_code_sent_at).total_seconds())
        if elapsed < CODE_RESEND_COOLDOWN_SECONDS:
            retry_after = CODE_RESEND_COOLDOWN_SECONDS - elapsed
            db.commit()
            raise HTTPException(
                status_code=429,
                detail=f"A code was already sent. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    _provider, delivery_ready, delivery_message = email_delivery_status()
    if not delivery_ready:
        db.rollback()
        raise HTTPException(status_code=503, detail=delivery_message)

    if not access:
        access = SubscriberApiAccess(
            id=str(uuid4()),
            subscriber_id=subscriber.user_uuid,
            subscriber_email=email,
            subscriber_is_active=True,
            quota_total=API_QUOTA,
            requests_used=0,
            is_key_active=False,
            created_at=now,
            updated_at=now,
        )
        db.add(access)
        db.flush()
    else:
        access.subscriber_id = subscriber.user_uuid
        access.subscriber_is_active = True

    code = f"{secrets.randbelow(1_000_000):06d}"
    access.verification_code_hash = secure_digest(f"code:{access.id}", code)
    access.verification_expires_at = now + timedelta(seconds=CODE_TTL_SECONDS)
    access.verification_attempts = 0
    access.last_code_sent_at = now
    access.last_code_request_ip_hash = ip_hash
    access.updated_at = now
    db.commit()

    try:
        deliver_email_message(_verification_message(email, code))
    except Exception as exc:
        logger.exception("student API verification email failed recipient=%s", email_hash[:12])
        access.verification_code_hash = None
        access.verification_expires_at = None
        access.updated_at = datetime.utcnow()
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="The verification email could not be sent. Please try again later.",
        ) from exc

    return {
        "status": "code_sent",
        "message": "A six-digit verification code was sent to your subscribed email.",
        "expires_in_seconds": CODE_TTL_SECONDS,
        "retry_after_seconds": CODE_RESEND_COOLDOWN_SECONDS,
    }


def verify_code(db: Session, request: Request, raw_email: str, code: str) -> dict:
    email = validate_email(raw_email)
    now = datetime.utcnow()
    ip_hash = _scope_hash("ip", client_ip(request))
    email_hash = _scope_hash("email", email)
    enforce_security_limits(
        db,
        (
            (ip_hash, "code_verify_ip", 30, 3600),
            (email_hash, "code_verify_email", 10, 3600),
        ),
    )
    subscriber = db.execute(
        select(EmailSubscriber).where(
            EmailSubscriber.subscribed_email == email,
            EmailSubscriber.is_active.is_(True),
        )
    ).scalar_one_or_none()
    access = db.execute(
        select(SubscriberApiAccess).where(SubscriberApiAccess.subscriber_email == email)
    ).scalar_one_or_none()
    if not subscriber or not access:
        db.commit()
        raise HTTPException(status_code=403, detail="An active newsletter subscription is required.")
    if (
        not access.verification_code_hash
        or not access.verification_expires_at
        or access.verification_expires_at < now
    ):
        access.verification_code_hash = None
        access.verification_expires_at = None
        access.updated_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="The verification code is invalid or expired.")
    if access.verification_attempts >= MAX_CODE_ATTEMPTS:
        access.verification_code_hash = None
        access.verification_expires_at = None
        access.updated_at = now
        db.commit()
        raise HTTPException(status_code=429, detail="Too many incorrect code attempts. Request a new code.")

    expected = secure_digest(f"code:{access.id}", code)
    if not hmac.compare_digest(expected, access.verification_code_hash):
        access.verification_attempts += 1
        attempts_left = max(0, MAX_CODE_ATTEMPTS - access.verification_attempts)
        if attempts_left == 0:
            access.verification_code_hash = None
            access.verification_expires_at = None
        access.updated_at = now
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"The verification code is incorrect. {attempts_left} attempt(s) remaining.",
        )

    raw_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    access.api_key_hash = secure_digest("api-key", raw_key)
    access.api_key_prefix = raw_key[:18]
    access.api_key_created_at = now
    access.verified_at = now
    access.subscriber_id = subscriber.user_uuid
    access.subscriber_is_active = True
    access.is_key_active = True
    access.verification_code_hash = None
    access.verification_expires_at = None
    access.verification_attempts = 0
    access.updated_at = now
    db.commit()
    remaining = max(0, access.quota_total - access.requests_used)
    return {
        "status": "verified",
        "message": "Email verified. Copy this API key now; it will not be shown again.",
        "api_key": raw_key,
        "key_prefix": access.api_key_prefix,
        "quota_total": access.quota_total,
        "requests_used": access.requests_used,
        "requests_remaining": remaining,
        "documentation_url": f"{canonical_site_url()}/tools/api",
    }


def _extract_api_key(request: Request) -> str:
    key = (request.headers.get("x-api-key") or "").strip()
    if not key:
        authorization = (request.headers.get("authorization") or "").strip()
        scheme, _space, value = authorization.partition(" ")
        if scheme.casefold() == "bearer":
            key = value.strip()
    if not key or len(key) > 160 or not re.fullmatch(r"pjm_live_[A-Za-z0-9_-]{30,120}", key):
        raise HTTPException(status_code=401, detail="A valid API key is required.")
    return key


def authenticate_api_key(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    *,
    consume_quota: bool,
) -> SubscriberApiAccess:
    raw_key = _extract_api_key(request)
    key_hash = secure_digest("api-key", raw_key)
    access = db.execute(
        select(SubscriberApiAccess).where(
            SubscriberApiAccess.api_key_hash == key_hash,
            SubscriberApiAccess.is_key_active.is_(True),
        )
    ).scalar_one_or_none()
    if not access:
        raise HTTPException(status_code=401, detail="The API key is invalid or inactive.")

    subscriber = db.execute(
        select(EmailSubscriber).where(
            EmailSubscriber.subscribed_email == access.subscriber_email,
            EmailSubscriber.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if not subscriber:
        access.subscriber_is_active = False
        access.is_key_active = False
        access.updated_at = datetime.utcnow()
        db.commit()
        raise HTTPException(
            status_code=403,
            detail="This newsletter subscription is inactive. Subscribe again to request access.",
        )

    ip_hash = _scope_hash("ip", client_ip(request))
    enforce_security_limits(
        db,
        (
            (ip_hash, "api_request_ip", 90, 60),
            (_scope_hash("key", key_hash), "api_request_key", 60, 60),
        ),
    )
    now = datetime.utcnow()
    if consume_quota:
        result = db.execute(
            update(SubscriberApiAccess)
            .where(
                SubscriberApiAccess.id == access.id,
                SubscriberApiAccess.is_key_active.is_(True),
                SubscriberApiAccess.requests_used < SubscriberApiAccess.quota_total,
            )
            .values(
                requests_used=SubscriberApiAccess.requests_used + 1,
                api_key_last_used_at=now,
                last_request_ip_hash=ip_hash,
                subscriber_is_active=True,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            db.commit()
            raise HTTPException(
                status_code=429,
                detail="API quota exhausted. Each subscriber receives 50 total data requests.",
            )
        db.commit()
        db.refresh(access)
    else:
        access.subscriber_is_active = True
        access.updated_at = now
        db.commit()

    remaining = max(0, access.quota_total - access.requests_used)
    response.headers["X-Quota-Limit"] = str(access.quota_total)
    response.headers["X-Quota-Used"] = str(access.requests_used)
    response.headers["X-Quota-Remaining"] = str(remaining)
    return access


def consume_student_api_request(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SubscriberApiAccess:
    return authenticate_api_key(request, response, db, consume_quota=True)


def inspect_student_api_quota(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SubscriberApiAccess:
    return authenticate_api_key(request, response, db, consume_quota=False)


def purge_old_security_events(db: Session) -> None:
    db.execute(
        delete(StudentApiSecurityEvent).where(
            StudentApiSecurityEvent.occurred_at < datetime.utcnow() - timedelta(days=7)
        )
    )
