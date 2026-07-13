from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    ensure_admin_user,
    get_current_admin,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.logging_config import get_logger
from app.models import User
from app.schemas import LoginIn, PasswordChangeIn, TokenOut

router = APIRouter()
logger = get_logger("jobportal.auth_router")


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    try:
        ensure_admin_user(db)
        user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
        if not user or not verify_password(payload.password, user.password_hash):
            logger.warning("login failed username=%s", payload.username)
            raise HTTPException(status_code=401, detail="Invalid username or password")
        token = create_access_token(user.username)
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
    db.commit()
    logger.info("admin password changed username=%s", admin.username)
    return {"ok": True}
