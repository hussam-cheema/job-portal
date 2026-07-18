from __future__ import annotations

from datetime import datetime
from math import ceil
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.database import get_db
from app.logging_config import get_logger
from app.models import BlogPost, User
from app.schemas import (
    BlogFiltersResponse,
    BlogPostIn,
    BlogPostListResponse,
    BlogPostOut,
    BlogPostUpdate,
)
from app.services.seo import delete_seo, upsert_blog_seo
from app.utils import slugify

router = APIRouter()
logger = get_logger("jobportal.blog")


def _public_filter(stmt):
    now = datetime.utcnow()
    return stmt.where(
        BlogPost.is_published.is_(True),
        or_(BlogPost.published_at.is_(None), BlogPost.published_at <= now),
    )


def _apply_filters(stmt, q: str | None, category: str | None, tag: str | None):
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                BlogPost.title.ilike(term),
                BlogPost.excerpt.ilike(term),
                BlogPost.content.ilike(term),
            )
        )
    if category:
        stmt = stmt.where(func.lower(BlogPost.category) == category.strip().lower())
    if tag:
        stmt = stmt.where(cast(BlogPost.tags, String).ilike(f'%"{tag.strip()}"%'))
    return stmt


@router.get("/blog", response_model=BlogPostListResponse)
def list_blog_posts(
    q: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=150),
    tag: str | None = Query(default=None, max_length=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    try:
        base = _apply_filters(_public_filter(select(BlogPost)), q, category, tag)
        total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
        items = db.execute(
            base.order_by(
                BlogPost.published_at.desc().nullslast(), BlogPost.created_at.desc()
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars().all()
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": ceil(total / page_size) if total else 0,
        }
    except Exception:
        logger.exception("list_blog_posts failed")
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}


@router.get("/blog/filters", response_model=BlogFiltersResponse)
def blog_filters(db: Session = Depends(get_db)):
    try:
        posts = db.execute(_public_filter(select(BlogPost))).scalars().all()
        return {
            "categories": sorted({p.category for p in posts if p.category}),
            "tags": sorted({str(tag) for p in posts for tag in (p.tags or []) if tag}),
        }
    except Exception:
        logger.exception("blog_filters failed")
        return {"categories": [], "tags": []}


@router.get("/blog/{slug}", response_model=BlogPostOut)
def get_blog_post(slug: str, db: Session = Depends(get_db)):
    try:
        post = db.execute(
            _public_filter(select(BlogPost)).where(BlogPost.slug == slug)
        ).scalar_one_or_none()
        if not post:
            raise HTTPException(status_code=404, detail="Blog post not found")
        return post
    except HTTPException:
        raise
    except Exception:
        logger.exception("get_blog_post failed slug=%s", slug)
        raise HTTPException(status_code=500, detail="Failed to load blog post") from None


@router.get("/admin/blog", response_model=BlogPostListResponse)
def admin_list_blog_posts(
    q: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=150),
    status: str | None = Query(default=None, pattern="^(published|draft)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        stmt = _apply_filters(select(BlogPost), q, category, None)
        if status == "published":
            stmt = stmt.where(BlogPost.is_published.is_(True))
        elif status == "draft":
            stmt = stmt.where(BlogPost.is_published.is_(False))
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = db.execute(
            stmt.order_by(BlogPost.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars().all()
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": ceil(total / page_size) if total else 0,
        }
    except Exception:
        logger.exception("admin_list_blog_posts failed")
        raise HTTPException(status_code=500, detail="Failed to load blog posts") from None


@router.get("/admin/blog/{post_id}", response_model=BlogPostOut)
def admin_get_blog_post(
    post_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    post = db.get(BlogPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    return post


@router.post("/admin/blog", response_model=BlogPostOut)
def create_blog_post(
    payload: BlogPostIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        slug = slugify(payload.slug or payload.title)
        if not slug:
            raise HTTPException(status_code=400, detail="A valid slug is required")
        if db.execute(select(BlogPost).where(BlogPost.slug == slug)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Slug already exists")
        now = datetime.utcnow()
        post = BlogPost(
            id=str(uuid4()),
            slug=slug,
            title=payload.title.strip(),
            excerpt=(payload.excerpt or "").strip() or None,
            content=payload.content or "",
            author=(payload.author or "").strip() or None,
            category=(payload.category or "").strip() or None,
            tags=list(dict.fromkeys(t.strip() for t in payload.tags if t.strip())),
            is_published=payload.is_published,
            published_at=payload.published_at or (now if payload.is_published else None),
            created_at=now,
            updated_at=now,
        )
        db.add(post)
        upsert_blog_seo(db, post, payload.seo.model_dump() if payload.seo else None)
        db.commit()
        db.refresh(post)
        return post
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("create_blog_post failed")
        raise HTTPException(status_code=500, detail="Failed to create blog post") from None


@router.put("/admin/blog/{post_id}", response_model=BlogPostOut)
def update_blog_post(
    post_id: str,
    payload: BlogPostUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        post = db.get(BlogPost, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Blog post not found")
        data = payload.model_dump(exclude_unset=True)
        seo_override = data.pop("seo", None)
        if data.get("slug"):
            candidate = slugify(data["slug"])
            duplicate = db.execute(
                select(BlogPost).where(BlogPost.slug == candidate, BlogPost.id != post_id)
            ).scalar_one_or_none()
            if duplicate:
                raise HTTPException(status_code=400, detail="Slug already exists")
            data["slug"] = candidate
        if "tags" in data and data["tags"] is not None:
            data["tags"] = list(dict.fromkeys(t.strip() for t in data["tags"] if t.strip()))
        was_published = post.is_published
        for key, value in data.items():
            setattr(post, key, value)
        if post.is_published and not post.published_at:
            post.published_at = datetime.utcnow()
        if not was_published and post.is_published and "published_at" not in data:
            post.published_at = datetime.utcnow()
        post.updated_at = datetime.utcnow()
        upsert_blog_seo(
            db, post, seo_override if isinstance(seo_override, dict) else None
        )
        db.commit()
        db.refresh(post)
        return post
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("update_blog_post failed id=%s", post_id)
        raise HTTPException(status_code=500, detail="Failed to update blog post") from None


@router.delete("/admin/blog/{post_id}")
def delete_blog_post(
    post_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        post = db.get(BlogPost, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Blog post not found")
        delete_seo(db, "blog", post_id)
        db.delete(post)
        db.commit()
        return {"ok": True, "id": post_id}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("delete_blog_post failed id=%s", post_id)
        raise HTTPException(status_code=500, detail="Failed to delete blog post") from None
