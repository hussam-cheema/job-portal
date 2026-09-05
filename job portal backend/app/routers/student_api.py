from __future__ import annotations

import html
import re
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BlogPost, Job, JobAttachment, SubscriberApiAccess
from app.schemas import (
    StudentApiCodeRequestIn,
    StudentApiCodeRequestOut,
    StudentApiCodeVerifyIn,
    StudentApiKeyOut,
    StudentApiQuotaOut,
)
from app.services.student_api import (
    consume_student_api_request,
    inspect_student_api_quota,
    request_verification_code,
    verify_code,
)

router = APIRouter()
_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_IMAGE_PATTERN = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*(['\"])(.*?)\1",
    re.IGNORECASE | re.DOTALL,
)


def _quota(access: SubscriberApiAccess) -> dict:
    return {
        "limit": access.quota_total,
        "used": access.requests_used,
        "remaining": max(0, access.quota_total - access.requests_used),
    }


def _advertisement_images(description: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for _quote, raw_url in _IMAGE_PATTERN.findall(description or ""):
        url = html.unescape(raw_url.strip())
        if url and url not in seen:
            seen.add(url)
            result.append(url)
    return result


def _job_payload(job: Job, attachments: list[JobAttachment]) -> dict:
    return {
        "id": job.id,
        "slug": job.slug,
        "title": job.title,
        "description": job.description,
        "advertisement_images": _advertisement_images(job.description),
        "published_date": job.published_date,
        "deadline_date": job.deadline_date,
        "salary_range": job.salary_range,
        "source": job.source,
        "newspaper": job.newspaper,
        "reference_url": job.reference_url,
        "application_url": job.application_url,
        "experience_required": job.experience_required,
        "education_required": job.education_required,
        "skills": job.skills or [],
        "job_type": job.job_type,
        "cities": job.cities or [],
        "provinces": job.provinces or [],
        "tags": job.tags or [],
        "keywords": job.keywords,
        "attachments": [
            {
                "id": item.id,
                "file_type": item.file_type,
                "file_size": item.file_size,
                "original_name": item.original_name,
                "is_inline_image": item.is_inline_image,
                "public_url": item.public_url,
                "created_at": item.created_at,
            }
            for item in attachments
        ],
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _blog_payload(post: BlogPost) -> dict:
    return {
        "id": post.id,
        "slug": post.slug,
        "title": post.title,
        "excerpt": post.excerpt,
        "content": post.content,
        "author": post.author,
        "category": post.category,
        "tags": post.tags or [],
        "is_published": post.is_published,
        "published_at": post.published_at,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    }


@router.post(
    "/student-api/request-code",
    response_model=StudentApiCodeRequestOut,
)
def student_api_request_code(
    payload: StudentApiCodeRequestIn,
    request: Request,
    db: Session = Depends(get_db),
):
    return request_verification_code(db, request, payload.email)


@router.post(
    "/student-api/verify-code",
    response_model=StudentApiKeyOut,
)
def student_api_verify_code(
    payload: StudentApiCodeVerifyIn,
    request: Request,
    db: Session = Depends(get_db),
):
    return verify_code(db, request, payload.email, payload.code)


@router.get("/student/v1/quota", response_model=StudentApiQuotaOut)
def student_api_quota(
    access: SubscriberApiAccess = Depends(inspect_student_api_quota),
):
    return {
        "key_prefix": access.api_key_prefix or "",
        "subscriber_email": access.subscriber_email,
        "quota_total": access.quota_total,
        "requests_used": access.requests_used,
        "requests_remaining": max(0, access.quota_total - access.requests_used),
        "is_active": access.is_key_active and access.subscriber_is_active,
        "created_at": access.api_key_created_at,
        "last_used_at": access.api_key_last_used_at,
    }


@router.get("/student/v1/jobs")
def student_api_jobs(
    q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=25),
    db: Session = Depends(get_db),
    access: SubscriberApiAccess = Depends(consume_student_api_request),
):
    stmt = select(Job)
    count_stmt = select(func.count()).select_from(Job)
    if q:
        term = f"%{q.strip()}%"
        condition = or_(Job.title.ilike(term), Job.source.ilike(term), Job.description.ilike(term))
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    total = db.execute(count_stmt).scalar() or 0
    jobs = db.execute(
        stmt.order_by(Job.published_date.desc(), Job.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    attachment_rows = db.execute(
        select(JobAttachment)
        .where(JobAttachment.job_id.in_([job.id for job in jobs]))
        .order_by(JobAttachment.created_at.asc())
    ).scalars().all() if jobs else []
    attachments: dict[str, list[JobAttachment]] = {}
    for item in attachment_rows:
        attachments.setdefault(item.job_id, []).append(item)
    return {
        "items": [_job_payload(job, attachments.get(job.id, [])) for job in jobs],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": ceil(total / page_size) if total else 0,
        },
        "quota": _quota(access),
    }


@router.get("/student/v1/jobs/{slug}")
def student_api_job(
    slug: str = Path(..., min_length=1, max_length=400, pattern=_SLUG_PATTERN),
    db: Session = Depends(get_db),
    access: SubscriberApiAccess = Depends(consume_student_api_request),
):
    job = db.execute(select(Job).where(Job.slug == slug)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job post not found.")
    attachments = db.execute(
        select(JobAttachment)
        .where(JobAttachment.job_id == job.id)
        .order_by(JobAttachment.created_at.asc())
    ).scalars().all()
    return {"item": _job_payload(job, attachments), "quota": _quota(access)}


def _published_blogs(stmt):
    from datetime import datetime

    now = datetime.utcnow()
    return stmt.where(
        BlogPost.is_published.is_(True),
        or_(BlogPost.published_at.is_(None), BlogPost.published_at <= now),
    )


@router.get("/student/v1/blog-posts")
def student_api_blogs(
    q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=25),
    db: Session = Depends(get_db),
    access: SubscriberApiAccess = Depends(consume_student_api_request),
):
    stmt = _published_blogs(select(BlogPost))
    count_stmt = _published_blogs(select(func.count()).select_from(BlogPost))
    if q:
        term = f"%{q.strip()}%"
        condition = or_(BlogPost.title.ilike(term), BlogPost.excerpt.ilike(term), BlogPost.content.ilike(term))
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    total = db.execute(count_stmt).scalar() or 0
    posts = db.execute(
        stmt.order_by(BlogPost.published_at.desc().nullslast(), BlogPost.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return {
        "items": [_blog_payload(post) for post in posts],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": ceil(total / page_size) if total else 0,
        },
        "quota": _quota(access),
    }


@router.get("/student/v1/blog-posts/{slug}")
def student_api_blog(
    slug: str = Path(..., min_length=1, max_length=400, pattern=_SLUG_PATTERN),
    db: Session = Depends(get_db),
    access: SubscriberApiAccess = Depends(consume_student_api_request),
):
    post = db.execute(
        _published_blogs(select(BlogPost)).where(BlogPost.slug == slug)
    ).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found.")
    return {"item": _blog_payload(post), "quota": _quota(access)}
