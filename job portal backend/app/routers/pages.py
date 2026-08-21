from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.database import get_db
from app.logging_config import get_logger
from app.models import Job, Page, User
from app.page_types import DIRECTORY_PAGE_PATHS, VALID_PAGE_TYPES, page_slug_namespace
from app.schemas import DirectoryPageLinkOut, PageIn, PageOut, PageUpdate
from app.seed import ensure_default_pages, sync_taxonomy_pages_v1
from app.services.seo import delete_seo, upsert_page_seo
from app.utils import slugify

router = APIRouter()
logger = get_logger("jobportal.pages")


def _page_identity(page_type: str | None, taxonomy_value: str | None) -> tuple[str, str | None]:
    normalized_type = (page_type or "standard").strip().lower()
    if normalized_type not in VALID_PAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid page type")
    normalized_value = (taxonomy_value or "").strip() or None
    if normalized_type in DIRECTORY_PAGE_PATHS and not normalized_value:
        raise HTTPException(
            status_code=400,
            detail="A matching taxonomy value is required for directory pages",
        )
    if normalized_type == "standard":
        normalized_value = None
    return normalized_type, normalized_value


def _slug_page_types(page_type: str) -> set[str]:
    return {"city", "province"} if page_slug_namespace(page_type) == "location" else {page_type}


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


@router.get("/pages/directory-links", response_model=list[DirectoryPageLinkOut])
def list_directory_page_links(db: Session = Depends(get_db)):
    if sync_taxonomy_pages_v1(db):
        db.commit()
    active_organization = exists(
        select(1).select_from(Job).where(
            func.lower(func.trim(Job.source))
            == func.lower(func.trim(Page.taxonomy_value))
        )
    )
    active_newspaper = exists(
        select(1).select_from(Job).where(
            func.lower(func.trim(Job.newspaper))
            == func.lower(func.trim(Page.taxonomy_value))
        )
    )
    rows = db.execute(
        select(
            Page.id,
            Page.slug,
            Page.title,
            Page.page_type,
            Page.taxonomy_value,
        )
        .where(
            Page.page_type != "standard",
            Page.taxonomy_value.is_not(None),
            Page.is_published.is_(True),
            or_(
                Page.page_type.notin_({"organization", "newspaper"}),
                and_(Page.page_type == "organization", active_organization),
                and_(Page.page_type == "newspaper", active_newspaper),
            ),
        )
        .order_by(Page.page_type.asc(), Page.title.asc())
    ).all()
    return [
        DirectoryPageLinkOut(
            id=row.id,
            slug=row.slug,
            title=row.title,
            page_type=row.page_type,
            taxonomy_value=row.taxonomy_value,
        )
        for row in rows
    ]


@router.get("/pages/{slug}", response_model=PageOut)
def get_page(slug: str, db: Session = Depends(get_db)):
    try:
        page = db.execute(
            select(Page).where(
                Page.slug == slug,
                Page.page_type == "standard",
                Page.is_published.is_(True),
            )
        ).scalar_one_or_none()
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        return page
    except HTTPException:
        raise
    except Exception:
        logger.exception("get_page failed slug=%s", slug)
        raise HTTPException(status_code=500, detail="Failed to load page") from None


@router.get("/pages/directory/{page_type}/{slug}", response_model=PageOut)
def get_directory_page(page_type: str, slug: str, db: Session = Depends(get_db)):
    normalized_type = page_type.strip().lower()
    allowed_types = (
        {"city", "province"}
        if normalized_type == "location"
        else {normalized_type}
    )
    if not allowed_types.issubset(DIRECTORY_PAGE_PATHS):
        raise HTTPException(status_code=404, detail="Directory page not found")
    page = db.execute(
        select(Page).where(
            Page.page_type.in_(allowed_types),
            Page.slug == slug,
            Page.is_published.is_(True),
        )
    ).scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Directory page not found")
    return page


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
        page_type, taxonomy_value = _page_identity(
            payload.page_type, payload.taxonomy_value
        )
        exists = db.execute(
            select(Page).where(
                Page.slug == slug,
                Page.page_type.in_(_slug_page_types(page_type)),
            )
        ).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=400, detail="Slug already exists")
        if taxonomy_value:
            duplicate_taxonomy = db.execute(
                select(Page).where(
                    Page.page_type == page_type,
                    func.lower(Page.taxonomy_value) == taxonomy_value.lower(),
                )
            ).scalar_one_or_none()
            if duplicate_taxonomy:
                raise HTTPException(
                    status_code=400,
                    detail="A page already exists for this directory value",
                )
        page = Page(
            id=str(uuid4()),
            slug=slug,
            title=payload.title.strip(),
            content=payload.content or "",
            page_type=page_type,
            taxonomy_value=taxonomy_value,
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
        page_type, taxonomy_value = _page_identity(
            data.pop("page_type", page.page_type),
            data.pop("taxonomy_value", page.taxonomy_value),
        )
        if taxonomy_value:
            duplicate_taxonomy = db.execute(
                select(Page).where(
                    Page.page_type == page_type,
                    func.lower(Page.taxonomy_value) == taxonomy_value.lower(),
                    Page.id != page_id,
                )
            ).scalar_one_or_none()
            if duplicate_taxonomy:
                raise HTTPException(
                    status_code=400,
                    detail="A page already exists for this directory value",
                )
        page.page_type = page_type
        page.taxonomy_value = taxonomy_value
        candidate = slugify(data.pop("slug", page.slug))
        duplicate = db.execute(
            select(Page).where(
                Page.slug == candidate,
                Page.page_type.in_(_slug_page_types(page_type)),
                Page.id != page_id,
            )
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
