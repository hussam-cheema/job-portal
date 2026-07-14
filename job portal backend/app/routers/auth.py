from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    ensure_admin_user,
    get_current_admin,
    hash_password,
    jwt_secret,
    verify_password,
)
from app.database import get_db
from app.config import env
from app.logging_config import get_logger
from app.models import PasswordResetAttempt, User
from app.schemas import (
    CredentialsResetIn,
    LoginIn,
    PasswordChangeIn,
    PasswordResetRequestOut,
    TokenOut,
)
from app.services.auth_recovery import issue_password_reset, user_for_reset_token

router = APIRouter()
logger = get_logger("jobportal.auth_router")


def _requester_hash(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    address = request.headers.get("cf-connecting-ip") or forwarded
    if not address and request.client:
        address = request.client.host
    identity = address or "unknown"
    return hmac.new(jwt_secret().encode(), identity.encode(), hashlib.sha256).hexdigest()


def _record_recovery_attempt(request: Request, db: Session) -> None:
    now = datetime.utcnow()
    hourly_limit = int(env("PASSWORD_RESET_MAX_REQUESTS_PER_IP_HOUR", "5") or "5")
    global_hourly_limit = int(env("PASSWORD_RESET_MAX_REQUESTS_PER_HOUR", "10") or "10")
    requester_hash = _requester_hash(request)
    cutoff = now.replace(microsecond=0) - timedelta(hours=1)
    cleanup_cutoff = now.replace(microsecond=0) - timedelta(days=1)
    db.execute(delete(PasswordResetAttempt).where(PasswordResetAttempt.attempted_at < cleanup_cutoff))
    attempts = db.execute(
        select(func.count(PasswordResetAttempt.id)).where(
            PasswordResetAttempt.requester_hash == requester_hash,
            PasswordResetAttempt.attempted_at >= cutoff,
        )
    ).scalar_one()
    total_attempts = db.execute(
        select(func.count(PasswordResetAttempt.id)).where(
            PasswordResetAttempt.attempted_at >= cutoff,
        )
    ).scalar_one()
    if attempts >= hourly_limit or total_attempts >= global_hourly_limit:
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many recovery requests. Try again later.",
            headers={"Retry-After": "3600"},
        )
    db.add(
        PasswordResetAttempt(
            id=str(uuid4()),
            requester_hash=requester_hash,
            attempted_at=now,
        )
    )
    db.commit()


def _clear_recovery_state(user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_at = None
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    user.password_reset_requested_at = None


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    try:
        ensure_admin_user(db)
        user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
        if not user:
            logger.warning("login failed username=%s", payload.username)
            raise HTTPException(status_code=401, detail="Invalid username or password")

        if user.locked_at:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked. Use the reset link sent to the recovery email.",
            )

        if not verify_password(payload.password, user.password_hash):
            user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
            max_failed_attempts = int(env("MAX_FAILED_LOGIN_ATTEMPTS", "3") or "3")
            is_locked = user.failed_login_attempts > max_failed_attempts
            if is_locked:
                user.locked_at = datetime.utcnow()
            db.commit()
            logger.warning(
                "login failed username=%s attempts=%s locked=%s",
                payload.username,
                user.failed_login_attempts,
                is_locked,
            )
            if is_locked:
                try:
                    issue_password_reset(
                        db,
                        user,
                        reason="account locked after repeated failed sign-in attempts",
                        bypass_cooldown=True,
                    )
                    detail = "Account locked. A credential reset link was sent to the recovery email."
                except Exception:
                    detail = (
                        "Account locked. The recovery email could not be sent; "
                        "use Forgot your password to try again."
                    )
                raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=detail)

            remaining = max_failed_attempts + 1 - user.failed_login_attempts
            raise HTTPException(
                status_code=401,
                detail=f"Invalid username or password. {remaining} attempt(s) remain before lockout.",
            )

        _clear_recovery_state(user)
        db.commit()
        token = create_access_token(user.username, user.auth_version)
        logger.info("login ok username=%s", user.username)
        return TokenOut(access_token=token, username=user.username)
    except HTTPException:
        raise
    except Exception:
        logger.exception("login error")
        raise HTTPException(status_code=500, detail="Login failed") from None


@router.get("/auth/me")
def me(admin: User = Depends(get_current_admin)):
    return {"username": admin.username, "is_admin": admin.is_admin}


@router.post("/auth/forgot-password", response_model=PasswordResetRequestOut)
def forgot_password(request: Request, db: Session = Depends(get_db)):
    try:
        _record_recovery_attempt(request, db)
        user = ensure_admin_user(db)
        delivered = issue_password_reset(db, user, reason="forgot password request")
        cooldown = int(env("PASSWORD_RESET_COOLDOWN_SECONDS", "60") or "60")
        if not delivered:
            return PasswordResetRequestOut(
                message=(
                    "A reset email was requested recently. Wait briefly before requesting another."
                ),
                retry_after_seconds=cooldown,
            )
        return PasswordResetRequestOut(
            message="A reset link has been sent to the administrator email.",
            retry_after_seconds=cooldown,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("forgot password email failed")
        raise HTTPException(
            status_code=503,
            detail="Unable to send the recovery email. Check the SMTP configuration and try again.",
        ) from None


@router.post("/auth/reset-credentials")
def reset_credentials(payload: CredentialsResetIn, db: Session = Depends(get_db)):
    user = user_for_reset_token(db, payload.token)
    if not user:
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired")

    username = payload.username.strip()
    conflict = db.execute(
        select(User).where(User.username == username, User.id != user.id)
    ).scalar_one_or_none()
    if conflict:
        raise HTTPException(status_code=409, detail="Username is already in use")

    user.username = username
    user.password_hash = hash_password(payload.new_password)
    user.auth_version = int(user.auth_version or 0) + 1
    _clear_recovery_state(user)
    db.commit()
    logger.info("admin credentials reset username=%s", username)
    return {"ok": True, "message": "Credentials updated. You can now sign in."}


@router.put("/admin/password")
def change_password(
    payload: PasswordChangeIn,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if not verify_password(payload.current_password, admin.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different")
    admin.password_hash = hash_password(payload.new_password)
    _clear_recovery_state(admin)
    db.commit()
    logger.info("admin password changed username=%s", admin.username)
    return {"ok": True}
