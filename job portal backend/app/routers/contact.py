from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.database import get_db
from app.logging_config import get_logger
from app.models import ContactMessage, User
from app.schemas import ContactIn, ContactOut
from app.services.contact_security import (
    client_ip,
    enforce_rate_limits,
    validate_contact_payload,
)

router = APIRouter()
logger = get_logger("jobportal.contact")


@router.post("/contact", response_model=ContactOut)
def submit_contact(
    payload: ContactIn,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        clean = validate_contact_payload(
            name=payload.name,
            email=payload.email,
            subject=payload.subject,
            message=payload.message,
        )
        ip = client_ip(request)
        enforce_rate_limits(db, email=clean["email"], ip=ip)

        msg = ContactMessage(
            id=str(uuid4()),
            name=clean["name"],
            email=clean["email"],
            subject=clean["subject"] or None,
            message=clean["message"],
            is_read=False,
            created_at=datetime.utcnow(),
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        logger.info("contact message received id=%s ip=%s", msg.id, ip)
        return msg
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("submit_contact failed")
        raise HTTPException(status_code=500, detail="Failed to submit message") from None


@router.get("/admin/contact", response_model=list[ContactOut])
def list_messages(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    try:
        return (
            db.execute(select(ContactMessage).order_by(ContactMessage.created_at.desc()))
            .scalars()
            .all()
        )
    except Exception:
        logger.exception("list_messages failed")
        return []


@router.get("/admin/contact/{msg_id}", response_model=ContactOut)
def get_message(msg_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    try:
        msg = db.get(ContactMessage, msg_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        if not msg.is_read:
            msg.is_read = True
            db.commit()
            db.refresh(msg)
        return msg
    except HTTPException:
        raise
    except Exception:
        logger.exception("get_message failed id=%s", msg_id)
        raise HTTPException(status_code=500, detail="Failed to load message") from None


@router.delete("/admin/contact/{msg_id}")
def delete_message(
    msg_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_admin)
):
    try:
        msg = db.get(ContactMessage, msg_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        db.delete(msg)
        db.commit()
        return {"ok": True, "id": msg_id}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("delete_message failed id=%s", msg_id)
        raise HTTPException(status_code=500, detail="Failed to delete message") from None
