from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.database import get_db
from app.logging_config import get_logger
from app.models import Page, User
from app.schemas import PageIn, PageOut, PageUpdate
from app.seed import ensure_default_pages
from app.services.seo import delete_seo, upsert_page_seo
from app.utils import slugify

router = APIRouter()
logger = get_logger("jobportal.pages")


@router.get("/pages", response_model=list[PageOut])
def list_pages(db: Session = Depends(get_db), published_only: bool = True):
    try:
        stmt = select(Page).order_by(Page.title.asc())
        if published_only:
            stmt = stmt.where(Page.is_published.is_(True))
        return db.execute(stmt).scalars().all()
    except Exception:
        logger.exception("list_pages failed")
        return []


@router.get("/pages/{slug}", response_model=PageOut)
def get_page(slug: str, db: Session = Depends(get_db)):
    try:
        page = db.execute(
            select(Page).where(Page.slug == slug, Page.is_published.is_(True))
        ).scalar_one_or_none()
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        return page
    except HTTPException:
        raise
    except Exception:
        logger.exception("get_page failed slug=%s", slug)
        raise HTTPException(status_code=500, detail="Failed to load page") from None


@router.get("/admin/pages", response_model=list[PageOut])
def admin_list_pages(db: Session = Depends(get_db), _: User = Depends(get_current_admin)):
    try:
        if ensure_default_pages(db):
            db.commit()
        return db.execute(select(Page).order_by(Page.updated_at.desc())).scalars().all()
    except Exception:
        logger.exception("admin_list_pages failed")
        raise HTTPException(status_code=500, detail="Failed to load pages") from None


@router.post("/admin/pages", response_model=PageOut)
def create_page(
    payload: PageIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        slug = slugify(payload.slug or payload.title)
        exists = db.execute(select(Page).where(Page.slug == slug)).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=400, detail="Slug already exists")
        page = Page(
            id=str(uuid4()),
            slug=slug,
            title=payload.title.strip(),
            content=payload.content or "",
            is_published=payload.is_published,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(page)
        seo_ov = payload.seo.model_dump() if payload.seo else None
        upsert_page_seo(db, page, seo_override=seo_ov)
        db.commit()
        db.refresh(page)
        logger.info("page created slug=%s", page.slug)
        return page
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("create_page failed")
        raise HTTPException(status_code=500, detail="Failed to create page") from None


@router.put("/admin/pages/{page_id}", response_model=PageOut)
def update_page(
    page_id: str,
    payload: PageUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        page = db.get(Page, page_id)
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        data = payload.model_dump(exclude_unset=True)
        seo_ov = data.pop("seo", None)
        if "slug" in data and data["slug"]:
            candidate = slugify(data["slug"])
            duplicate = db.execute(
                select(Page).where(Page.slug == candidate, Page.id != page_id)
            ).scalar_one_or_none()
            if duplicate:
                raise HTTPException(status_code=400, detail="Slug already exists")
            page.slug = candidate
        if "title" in data and data["title"] is not None:
            page.title = data["title"]
        if "content" in data and data["content"] is not None:
            page.content = data["content"]
        if "is_published" in data and data["is_published"] is not None:
            page.is_published = data["is_published"]
        page.updated_at = datetime.utcnow()
        upsert_page_seo(db, page, seo_override=seo_ov if isinstance(seo_ov, dict) else None)
        db.commit()
        db.refresh(page)
        return page
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("update_page failed id=%s", page_id)
        raise HTTPException(status_code=500, detail="Failed to update page") from None


@router.delete("/admin/pages/{page_id}")
def delete_page(
    page_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        page = db.get(Page, page_id)
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        delete_seo(db, "page", page_id)
        db.delete(page)
        db.commit()
        return {"ok": True, "id": page_id}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("delete_page failed id=%s", page_id)
        raise HTTPException(status_code=500, detail="Failed to delete page") from None
