from __future__ import annotations

import hashlib
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import env, site_url
from app.logging_config import get_logger
from app.models import User

logger = get_logger("jobportal.auth_recovery")

DEFAULT_RECOVERY_EMAIL = "hussam.cheema7102@gmail.com"


def _bool_env(name: str, default: bool) -> bool:
    raw = env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _reset_url(token: str) -> str:
    query = urlencode({"token": token})
    return f"{site_url().rstrip('/')}/reset-password?{query}"


def _send_password_reset_email(*, reset_url: str, reason: str) -> None:
    recipient = env("ADMIN_RECOVERY_EMAIL", DEFAULT_RECOVERY_EMAIL) or DEFAULT_RECOVERY_EMAIL
    smtp_host = env("SMTP_HOST")
    smtp_username = env("SMTP_USERNAME")
    smtp_password = env("SMTP_PASSWORD")
    if smtp_password and smtp_host.lower() == "smtp.gmail.com":
        # Google displays 16-character App Passwords grouped with spaces. Those
        # spaces are presentation-only and must not be sent to SMTP AUTH.
        smtp_password = "".join(smtp_password.split())
    from_email = env("SMTP_FROM_EMAIL") or smtp_username
    if not smtp_host or not from_email:
        raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL (or SMTP_USERNAME) must be configured")

    port = int(env("SMTP_PORT", "587") or "587")
    timeout = int(env("SMTP_TIMEOUT_SECONDS", "15") or "15")
    use_ssl = _bool_env("SMTP_USE_SSL", port == 465)
    starttls = _bool_env("SMTP_STARTTLS", not use_ssl)
    authenticate = _bool_env("SMTP_AUTH", bool(smtp_username))

    message = EmailMessage()
    message["Subject"] = "Reset your Job Portal admin credentials"
    message["From"] = from_email
    message["To"] = recipient
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=from_email.rpartition("@")[2] or None)
    message.set_content(
        "A Job Portal administrator credential reset was requested "
        f"({reason}).\n\nOpen this single-use link to choose a new username and password:\n"
        f"{reset_url}\n\nThe link expires soon. If you did not request it, do not open it."
    )
    message.add_alternative(
        "<p>A Job Portal administrator credential reset was requested "
        f"(<strong>{reason}</strong>).</p>"
        f'<p><a href="{reset_url}">Choose a new username and password</a></p>'
        "<p>This single-use link expires soon. If you did not request it, ignore this email.</p>",
        subtype="html",
    )

    context = ssl.create_default_context()
    if use_ssl:
        with smtplib.SMTP_SSL(smtp_host, port, timeout=timeout, context=context) as smtp:
            if authenticate:
                if not smtp_username:
                    raise RuntimeError("SMTP_USERNAME must be configured when SMTP_AUTH is enabled")
                if not smtp_password:
                    raise RuntimeError("SMTP_PASSWORD must be configured when SMTP_USERNAME is set")
                smtp.login(smtp_username, smtp_password)
            refused = smtp.send_message(message)
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)
        return

    with smtplib.SMTP(smtp_host, port, timeout=timeout) as smtp:
        smtp.ehlo()
        if starttls:
            smtp.starttls(context=context)
            smtp.ehlo()
        if authenticate:
            if not smtp_username:
                raise RuntimeError("SMTP_USERNAME must be configured when SMTP_AUTH is enabled")
            if not smtp_password:
                raise RuntimeError("SMTP_PASSWORD must be configured when SMTP_USERNAME is set")
            smtp.login(smtp_username, smtp_password)
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


def issue_password_reset(
    db: Session,
    user: User,
    *,
    reason: str,
    bypass_cooldown: bool = False,
) -> bool:
    """Issue and email a single-use reset token. Returns False during the resend cooldown."""
    now = datetime.utcnow()
    cooldown_seconds = int(env("PASSWORD_RESET_COOLDOWN_SECONDS", "60") or "60")
    if (
        not bypass_cooldown
        and user.password_reset_requested_at
        and now - user.password_reset_requested_at < timedelta(seconds=cooldown_seconds)
    ):
        return False

    token = secrets.token_urlsafe(48)
    ttl_minutes = int(env("PASSWORD_RESET_TOKEN_TTL_MINUTES", "30") or "30")
    user.password_reset_token_hash = _token_hash(token)
    user.password_reset_expires_at = now + timedelta(minutes=ttl_minutes)
    user.password_reset_requested_at = now
    db.commit()

    try:
        _send_password_reset_email(reset_url=_reset_url(token), reason=reason)
    except Exception:
        logger.exception("password reset email delivery failed")
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        user.password_reset_requested_at = None
        db.commit()
        raise

    logger.info("password reset email sent reason=%s", reason)
    return True


def user_for_reset_token(db: Session, token: str) -> User | None:
    if len(token) < 20:
        return None
    user = db.execute(
        select(User).where(
            User.is_admin.is_(True),
            User.password_reset_token_hash == _token_hash(token),
        )
    ).scalar_one_or_none()
    if not user or not user.password_reset_expires_at:
        return None
    if user.password_reset_expires_at < datetime.utcnow():
        return None
    return user
