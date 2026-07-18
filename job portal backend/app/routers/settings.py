from __future__ import annotations

from io import BytesIO
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from PIL import Image

from app.auth import get_current_admin
from app.config import cfg, site_name
from app.database import get_db
from app.models import SiteSetting, User
from app.schemas import BrandingOut, BrandingUpdateIn
from app.services.storage import upload_bytes

router = APIRouter()


def _setting(db: Session, key: str) -> str | None:
    row = db.get(SiteSetting, key)
    return row.value if row else None


def _set_setting(db: Session, key: str, value: str | None) -> None:
    row = db.get(SiteSetting, key)
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        db.add(SiteSetting(key=key, value=value, updated_at=datetime.utcnow()))


def _site_title_alignment(db: Session) -> str:
    value = _setting(db, "site_title_alignment")
    return value if value in {"beside_logo", "center", "right"} else "center"


def _branding_response(db: Session) -> BrandingOut:
    return BrandingOut(
        site_name=site_name(),
        site_title=_setting(db, "site_title")
        or str(cfg("site", "title", default="PakJobs Jobs in Pakistan")),
        site_title_alignment=_site_title_alignment(db),
        site_header=_setting(db, "site_header")
        or str(
            cfg(
                "site",
                "header",
                default="Latest government & private job openings in Pakistan",
            )
        ),
        site_description=_setting(db, "site_description")
        or str(cfg("site", "description", default="Jobs in Pakistan")),
        footer_copyright=_setting(db, "footer_copyright")
        or str(
            cfg(
                "site",
                "footer_copyright",
                default="Copyrights © {year} - PakistanJobs All rights reserved",
            )
        ),
        logo_url=_setting(db, "logo_url"),
    )


@router.get("/settings/branding", response_model=BrandingOut)
def public_branding(db: Session = Depends(get_db)):
    return _branding_response(db)


@router.get("/admin/settings/branding", response_model=BrandingOut)
def admin_branding(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    return _branding_response(db)


@router.put("/admin/settings/branding", response_model=BrandingOut)
def update_branding(
    payload: BrandingUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    for key, value in payload.model_dump().items():
        _set_setting(db, key, value.strip())
    db.commit()
    return _branding_response(db)


@router.post("/admin/settings/logo", response_model=BrandingOut)
async def update_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    allowed = {"image/png", "image/jpeg", "image/webp", "image/gif"}
    content_type = (file.content_type or "").lower()
    if content_type not in allowed:
        raise HTTPException(status_code=400, detail="Use a PNG, JPG, WebP, or GIF image")
    raw = await file.read()
    max_mb = float(cfg("branding", "max_logo_mb", default=2) or 2)
    if not raw or len(raw) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Logo must be smaller than {max_mb:g}MB")
    try:
        with Image.open(BytesIO(raw)) as image:
            image.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Logo is not a valid image") from None
    try:
        uploaded = upload_bytes(
            raw,
            filename=file.filename or "logo.png",
            content_type=content_type,
            folder="branding",
        )
        _set_setting(db, "logo_url", uploaded["public_url"])
        db.commit()
        return _branding_response(db)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Logo upload failed") from None


@router.delete("/admin/settings/logo", response_model=BrandingOut)
def remove_logo(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    _set_setting(db, "logo_url", None)
    db.commit()
    return _branding_response(db)
