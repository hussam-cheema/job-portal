from __future__ import annotations

import hashlib
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import cfg
from app.logging_config import get_logger
from app.models import ContactMessage

logger = get_logger("jobportal.contact_security")

# Common legitimate providers (plus country TLDs for corporate email)
ALLOWED_EMAIL_PROVIDERS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.uk",
    "yahoo.co.in",
    "ymail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "protonmail.com",
    "proton.me",
    "aol.com",
    "mail.com",
    "zoho.com",
    "gmx.com",
    "gmx.net",
    "fastmail.com",
    "hey.com",
    "pm.me",
    # Pakistan common
    "hotmail.co.uk",
}

# Block known disposable / throwaway domains (subset)
DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "guerrillamail.com",
    "tempmail.com",
    "10minutemail.com",
    "trashmail.com",
    "yopmail.com",
    "sharklasers.com",
    "getnada.com",
    "temp-mail.org",
    "discard.email",
}

SQL_INJECTION_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"('\s*or\s+'1'\s*=\s*'1)",
        r"(--\s*$)",
        r"(;\s*drop\s+table)",
        r"(;\s*delete\s+from)",
        r"(union\s+select)",
        r"(insert\s+into)",
        r"(update\s+\w+\s+set)",
        r"(exec\s*\()",
        r"(xp_cmdshell)",
        r"(<script[\s>])",
        r"(javascript\s*:)",
        r"(onerror\s*=)",
    ]
]

# In-memory flood control (IP → timestamps)
_ip_hits: dict[str, list[float]] = defaultdict(list)
_email_hits: dict[str, list[float]] = defaultdict(list)


def _limits() -> dict:
    return {
        "name": int(cfg("contact", "max_name_len", default=50) or 50),
        "subject": int(cfg("contact", "max_subject_len", default=50) or 50),
        "email": int(cfg("contact", "max_email_len", default=100) or 100),
        "message": int(cfg("contact", "max_message_len", default=300) or 300),
        "day": int(cfg("contact", "max_messages_per_day", default=50) or 50),
        "ip_hour": int(cfg("contact", "max_per_ip_per_hour", default=5) or 5),
        "email_day": int(cfg("contact", "max_per_email_per_day", default=3) or 3),
    }


def sanitize_text(value: str, max_len: int) -> str:
    text = (value or "").strip()
    # Strip null bytes / control chars except newline/tab
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    # Collapse excessive whitespace
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_len]


def contains_injection(value: str) -> bool:
    if not value:
        return False
    for pat in SQL_INJECTION_PATTERNS:
        if pat.search(value):
            return True
    return False


def validate_email(email: str) -> str:
    limits = _limits()
    email = sanitize_text(email, limits["email"]).lower()
    if len(email) > limits["email"]:
        raise HTTPException(status_code=400, detail=f"Email must be ≤ {limits['email']} characters")
    if not re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    domain = email.split("@", 1)[1]
    if domain in DISPOSABLE_DOMAINS:
        raise HTTPException(status_code=400, detail="Disposable email addresses are not allowed")
    # Allow known providers OR corporate domains (have a real TLD, not disposable)
    if domain not in ALLOWED_EMAIL_PROVIDERS:
        # Corporate: must look like company.tld with at least one dot and no free-form junk
        if not re.fullmatch(r"[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)+", domain):
            raise HTTPException(status_code=400, detail="Email domain is not valid")
        # Reject single-label or weird
        if domain.count(".") < 1:
            raise HTTPException(status_code=400, detail="Email provider/domain is not accepted")
    return email


def validate_contact_payload(
    *,
    name: str,
    email: str,
    subject: Optional[str],
    message: str,
) -> dict[str, str]:
    limits = _limits()
    name = sanitize_text(name, limits["name"])
    subject_s = sanitize_text(subject or "", limits["subject"])
    message = sanitize_text(message, limits["message"])
    email = validate_email(email)

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if len(name) > limits["name"]:
        raise HTTPException(status_code=400, detail=f"Name must be ≤ {limits['name']} characters")
    if subject_s and len(subject_s) > limits["subject"]:
        raise HTTPException(
            status_code=400, detail=f"Subject must be ≤ {limits['subject']} characters"
        )
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    if len(message) > limits["message"]:
        raise HTTPException(
            status_code=400, detail=f"Message must be ≤ {limits['message']} characters"
        )

    for field, val in (("name", name), ("subject", subject_s), ("message", message), ("email", email)):
        if contains_injection(val):
            logger.warning("injection pattern blocked field=%s", field)
            raise HTTPException(status_code=400, detail="Invalid characters in form data")

    # Honeypot-ish: reject if message is only links or repeated chars
    if re.fullmatch(r"(.)\1{20,}", message.replace(" ", "")):
        raise HTTPException(status_code=400, detail="Message looks like spam")
    link_count = len(re.findall(r"https?://|www\.", message, re.I))
    if link_count > 3:
        raise HTTPException(status_code=400, detail="Too many links in message")

    return {
        "name": name,
        "email": email,
        "subject": subject_s,
        "message": message,
    }


def client_ip(request: Request | None) -> str:
    if not request:
        return "unknown"
    forwarded = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client:
        return (request.client.host or "unknown")[:64]
    return "unknown"


def _prune(ts_list: list[float], window_sec: float) -> list[float]:
    cutoff = time.time() - window_sec
    return [t for t in ts_list if t >= cutoff]


def enforce_rate_limits(
    db: Session,
    *,
    email: str,
    ip: str,
) -> None:
    limits = _limits()
    now = time.time()

    # Per-IP hourly
    hits = _prune(_ip_hits.get(ip, []), 3600)
    if len(hits) >= limits["ip_hour"]:
        logger.warning("rate_limit ip=%s", ip)
        raise HTTPException(
            status_code=429,
            detail=f"Too many messages from this network. Max {limits['ip_hour']} per hour.",
        )
    hits.append(now)
    _ip_hits[ip] = hits

    # Per-email daily (memory)
    ehits = _prune(_email_hits.get(email, []), 86400)
    if len(ehits) >= limits["email_day"]:
        raise HTTPException(
            status_code=429,
            detail=f"Too many messages from this email today. Max {limits['email_day']} per day.",
        )
    ehits.append(now)
    _email_hits[email] = ehits

    # Global daily cap (DB) — max 50 messages/day total
    try:
        since = datetime.utcnow() - timedelta(days=1)
        count = (
            db.execute(
                select(func.count())
                .select_from(ContactMessage)
                .where(ContactMessage.created_at >= since)
            ).scalar()
            or 0
        )
        if count >= limits["day"]:
            logger.warning("global daily contact cap reached count=%s", count)
            raise HTTPException(
                status_code=429,
                detail=f"Contact form daily limit reached ({limits['day']} messages). Try again tomorrow.",
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("daily cap check failed — allowing with caution")


def fingerprint(ip: str, email: str) -> str:
    return hashlib.sha256(f"{ip}|{email}".encode()).hexdigest()[:16]
