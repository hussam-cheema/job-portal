from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.config import cfg
from app.database import get_db
from app.logging_config import get_logger
from app.models import Job, JobAttachment, User
from app.schemas import JobAttachmentOut, UploadOut
from app.services.storage import resolve_local_path, upload_bytes
from app.services.watermark import apply_watermark

router = APIRouter()
logger = get_logger("jobportal.uploads")


def _is_image(content_type: str | None, filename: str) -> bool:
    ct = (content_type or "").lower()
    if ct.startswith("image/"):
        return True
    return filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))


@router.post("/admin/upload", response_model=UploadOut)
async def upload_file(
    file: UploadFile = File(...),
    job_id: str | None = Form(None),
    as_attachment: bool = Form(False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Empty file")

        filename = file.filename or "upload.bin"
        content_type = file.content_type or "application/octet-stream"
        is_image = _is_image(content_type, filename) and not as_attachment

        max_img = float(cfg("r2", "max_image_mb", default=8) or 8)
        max_att = float(cfg("r2", "max_attachment_mb", default=15) or 15)
        size_mb = len(raw) / (1024 * 1024)
        if is_image and size_mb > max_img:
            raise HTTPException(status_code=400, detail=f"Image exceeds {max_img}MB")
        if not is_image and size_mb > max_att:
            raise HTTPException(status_code=400, detail=f"Attachment exceeds {max_att}MB")

        if job_id and as_attachment:
            count = (
                db.execute(
                    select(func.count())
                    .select_from(JobAttachment)
                    .where(
                        JobAttachment.job_id == job_id,
                        JobAttachment.is_inline_image.is_(False),
                    )
                ).scalar()
                or 0
            )
            max_count = int(cfg("r2", "max_attachment_count", default=3) or 3)
            if count >= max_count:
                raise HTTPException(
                    status_code=400, detail=f"Max {max_count} attachments per job post"
                )
            if not db.get(Job, job_id):
                raise HTTPException(status_code=404, detail="Job not found")

        data = apply_watermark(raw, content_type) if is_image else raw
        folder = "images" if is_image else "attachments"
        # Store under the R2 prefix/{job_uuid}/images|attachments/.
        meta = upload_bytes(
            data,
            filename=filename,
            content_type=content_type,
            folder=folder,
            job_id=job_id,
        )

        attachment_id = None
        if job_id:
            row = JobAttachment(
                id=str(uuid4()),
                job_id=job_id,
                file_type=meta["file_type"],
                file_size=meta["file_size"],
                s3_path=meta["s3_path"],
                original_name=meta.get("original_name"),
                is_inline_image=is_image and not as_attachment,
                public_url=meta["public_url"],
                created_at=datetime.utcnow(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            attachment_id = row.id

        logger.info("upload ok name=%s image=%s job_id=%s", filename, is_image, job_id)
        return UploadOut(
            id=attachment_id,
            file_type=meta["file_type"],
            file_size=meta["file_size"],
            s3_path=meta["s3_path"],
            public_url=meta["public_url"],
            original_name=meta.get("original_name"),
            is_inline_image=is_image and not as_attachment,
        )
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("upload_file failed")
        raise HTTPException(status_code=500, detail="Upload failed") from None


@router.get("/admin/jobs/{job_id}/attachments", response_model=list[JobAttachmentOut])
def list_attachments(
    job_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_admin)
):
    try:
        return (
            db.execute(
                select(JobAttachment)
                .where(JobAttachment.job_id == job_id)
                .order_by(JobAttachment.created_at.desc())
            )
            .scalars()
            .all()
        )
    except Exception:
        logger.exception("list_attachments failed")
        return []


@router.delete("/admin/attachments/{attachment_id}")
def delete_attachment(
    attachment_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_admin)
):
    try:
        row = db.get(JobAttachment, attachment_id)
        if not row:
            raise HTTPException(status_code=404, detail="Attachment not found")
        db.delete(row)
        db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("delete_attachment failed")
        raise HTTPException(status_code=500, detail="Delete failed") from None


@router.get("/media/{file_path:path}")
def serve_media(file_path: str):
    try:
        path = resolve_local_path(file_path)
        if not path:
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(path)
    except HTTPException:
        raise
    except Exception:
        logger.exception("serve_media failed path=%s", file_path)
        raise HTTPException(status_code=500, detail="Failed to serve file") from None
