from __future__ import annotations

import math
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import cast, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.types import String

from app.auth import get_current_admin
from app.constants import DEFAULT_CATEGORIES, JOB_TYPES, PAKISTAN_CITIES, SECTORS
from app.database import get_db
from app.exceptions import empty_filters, empty_job_list
from app.logging_config import get_logger
from app.models import Job, JobAttachment, JobQnA, User
from app.schemas import (
    FiltersResponse,
    JobCreate,
    JobDetail,
    JobListResponse,
    JobQnAOut,
    JobSummary,
    JobUpdate,
    QnAFetchResult,
)
from app.services.qna import fetch_qna_for_job_title
from app.services.seo import delete_seo, upsert_job_seo
from app.utils import as_list, experience_label, normalize_job_type, slugify, strip_html

router = APIRouter()
logger = get_logger("jobportal.jobs")


def _list_field(value) -> list[str]:
    return as_list(value)


def _source_type(job: Job) -> str:
    jt = (job.job_type or "").lower()
    if jt in {"government", "govt", "gov"}:
        return "govt"
    return "private"


def _to_summary(job: Job) -> JobSummary:
    cities = _list_field(job.cities)
    tags = _list_field(job.tags)
    skills = _list_field(job.skills)
    # Build display tags
    display_tags = list(tags)
    if job.job_type:
        label = "Government" if _source_type(job) == "govt" else "Private"
        if label.lower() not in {t.lower() for t in display_tags}:
            display_tags.insert(0, label)
    for c in cities:
        if c.lower() not in {t.lower() for t in display_tags}:
            display_tags.append(c)
    for s in skills[:4]:
        if s.lower() not in {t.lower() for t in display_tags}:
            display_tags.append(s)

    return JobSummary(
        id=job.id,
        slug=job.slug,
        title=job.title,
        description=job.description,
        published_date=job.published_date,
        deadline_date=job.deadline_date,
        salary_range=job.salary_range,
        source=job.source,
        reference_url=job.reference_url,
        application_url=job.application_url,
        experience_required=job.experience_required,
        education_required=job.education_required,
        skills=skills,
        job_type=job.job_type,
        cities=cities,
        tags=display_tags,
        keywords=job.keywords,
        created_at=job.created_at,
        company=job.source,
        location=", ".join(cities) if cities else None,
        city=cities[0] if cities else None,
        province=None,
        employment_type=None,
        salary_min=None,
        salary_max=None,
        currency="PKR",
        category=tags[0] if tags else None,
        application_deadline=job.deadline_date,
        source_type=_source_type(job),
        source_name=job.source,
    )


def _to_detail(job: Job, db: Session) -> JobDetail:
    summary = _to_summary(job)
    try:
        attachments = (
            db.execute(
                select(JobAttachment)
                .where(JobAttachment.job_id == job.id)
                .order_by(JobAttachment.created_at.desc())
            )
            .scalars()
            .all()
        )
    except Exception:
        logger.exception("attachments load failed job_id=%s", job.id)
        attachments = []
    try:
        qna = (
            db.execute(
                select(JobQnA).where(JobQnA.job_id == job.id).order_by(JobQnA.created_at.asc())
            )
            .scalars()
            .all()
        )
    except Exception:
        logger.exception("qna load failed job_id=%s", job.id)
        qna = []

    # Compatibility resources shape for existing frontend QnA loader
    resources = []
    if qna:
        resources.append(
            {
                "id": f"qna-{job.id}",
                "job_id": job.id,
                "resource_type": "qna",
                "title": f"QnA — {job.title}",
                "url": qna[0].youtube_url or "",
                "description": "Commonly asked questions and answers",
                "file_type": "youtube",
                "content_text": None,
                "meta": {
                    "qna_items": [
                        {
                            "question": q.question,
                            "answer": q.answer,
                            "source": q.source,
                            "youtube_url": q.youtube_url,
                            "youtube_title": q.youtube_title,
                        }
                        for q in qna
                    ],
                    "qna_count": len(qna),
                },
                "created_at": qna[0].created_at,
            }
        )

    return JobDetail(
        **summary.model_dump(),
        application_email=None,
        source_url=job.reference_url or job.application_url or "",
        attachments=attachments,
        qna=[JobQnAOut.model_validate(q) for q in qna],
        resources=resources,
    )


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:10], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _unique_slug(db: Session, title: str, exclude_id: Optional[str] = None) -> str:
    base = slugify(title) or "job"
    candidate = base
    i = 2
    while True:
        q = select(Job).where(Job.slug == candidate)
        if exclude_id:
            q = q.where(Job.id != exclude_id)
        exists = db.execute(q).scalar_one_or_none()
        if not exists:
            return candidate
        candidate = f"{base}-{i}"
        i += 1


def _apply_job_fields(job: Job, data: dict, db: Session, *, is_create: bool) -> None:
    if "title" in data and data["title"] is not None:
        job.title = data["title"].strip()
        if is_create or not job.slug:
            job.slug = _unique_slug(db, job.title, exclude_id=None if is_create else job.id)
        elif data.get("title"):
            # keep slug stable on update unless empty
            pass
    if "description" in data and data["description"] is not None:
        job.description = data["description"]
    if "published_date" in data and data["published_date"] is not None:
        job.published_date = data["published_date"]
    if "deadline_date" in data:
        job.deadline_date = data["deadline_date"]
    if "salary_range" in data:
        job.salary_range = data["salary_range"]
    if "source" in data:
        job.source = data["source"]
    if "reference_url" in data:
        job.reference_url = data["reference_url"]
    if "application_url" in data:
        job.application_url = data["application_url"]
    if "experience_required" in data:
        job.experience_required = experience_label(data["experience_required"])
    if "education_required" in data:
        job.education_required = data["education_required"]
    if "skills" in data and data["skills"] is not None:
        job.skills = as_list(data["skills"])
    if "job_type" in data:
        job.job_type = normalize_job_type(data["job_type"])
    if "cities" in data and data["cities"] is not None:
        job.cities = as_list(data["cities"])
    if "tags" in data and data["tags"] is not None:
        job.tags = as_list(data["tags"])
    if "keywords" in data:
        job.keywords = data["keywords"]
    job.updated_at = datetime.utcnow()


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    q: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    employment_type: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        if date:
            date_from = date
            date_to = date

        stmt = select(Job)
        count_stmt = select(func.count()).select_from(Job)
        filters = []

        if q:
            like = f"%{q.strip()}%"
            filters.append(
                or_(
                    Job.title.ilike(like),
                    Job.description.ilike(like),
                    Job.source.ilike(like),
                    Job.keywords.ilike(like),
                    cast(Job.skills, String).ilike(like),
                    cast(Job.tags, String).ilike(like),
                    cast(Job.cities, String).ilike(like),
                )
            )
        if source_type or sector or job_type:
            raw = (job_type or sector or source_type or "").lower().strip()
            if raw in {"govt", "government", "gov"}:
                filters.append(Job.job_type.in_(["government", "govt", "gov"]))
            elif raw in {"private", "company", "newspaper"}:
                filters.append(
                    or_(Job.job_type.in_(["private", "company", "newspaper"]), Job.job_type.is_(None))
                )
        if category:
            like = f"%{category.strip()}%"
            filters.append(cast(Job.tags, String).ilike(like))
        if city:
            like = f"%{city.strip()}%"
            filters.append(cast(Job.cities, String).ilike(like))
        if company:
            filters.append(Job.source == company)
        if tag:
            t = tag.strip()
            t_lower = t.lower()
            if t_lower in {"government", "govt"}:
                filters.append(Job.job_type.in_(["government", "govt", "gov"]))
            elif t_lower == "private":
                filters.append(
                    or_(Job.job_type.in_(["private", "company"]), Job.job_type.is_(None))
                )
            else:
                like = f"%{t}%"
                filters.append(
                    or_(
                        cast(Job.tags, String).ilike(like),
                        cast(Job.skills, String).ilike(like),
                        cast(Job.cities, String).ilike(like),
                        Job.title.ilike(like),
                    )
                )

        df = _parse_date(date_from)
        dt = _parse_date(date_to)
        if df:
            filters.append(Job.published_date >= df)
        if dt:
            end = dt.replace(hour=23, minute=59, second=59)
            filters.append(Job.published_date <= end)

        for f in filters:
            stmt = stmt.where(f)
            count_stmt = count_stmt.where(f)

        total = db.execute(count_stmt).scalar() or 0
        pages = max(1, math.ceil(total / page_size)) if total else 0
        offset = (page - 1) * page_size
        rows = (
            db.execute(
                stmt.order_by(Job.published_date.desc().nullslast(), Job.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        logger.info("list_jobs total=%s page=%s tag=%s", total, page, tag)
        return JobListResponse(
            items=[_to_summary(j) for j in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )
    except Exception:
        logger.exception("list_jobs failed")
        return JobListResponse(**empty_job_list(page=page, page_size=page_size))


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str, response: Response, db: Session = Depends(get_db)):
    # Q&A refreshes mutate job details independently of the job row. Prevent
    # browsers/CDNs from serving the previous Q&A set after a successful refresh.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    try:
        job = db.get(Job, job_id)
        if not job:
            job = db.execute(select(Job).where(Job.slug == job_id)).scalar_one_or_none()
    except Exception:
        logger.exception("get_job db error id=%s", job_id)
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        return _to_detail(job, db)
    except Exception:
        logger.exception("get_job serialize failed id=%s", job_id)
        raise HTTPException(status_code=500, detail="Failed to load job") from None


@router.post("/admin/jobs", response_model=JobDetail)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        if not payload.title or not payload.description or not payload.published_date:
            raise HTTPException(status_code=400, detail="title, description, published_date required")
        job = Job(
            id=str(uuid4()),
            slug=_unique_slug(db, payload.title),
            title=payload.title.strip(),
            description=payload.description,
            published_date=payload.published_date,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        data = payload.model_dump()
        seo_ov = data.pop("seo", None) or {}
        if isinstance(seo_ov, dict) is False and hasattr(seo_ov, "model_dump"):
            seo_ov = seo_ov.model_dump()
        _apply_job_fields(job, data, db, is_create=True)
        db.add(job)
        upsert_job_seo(db, job, seo_override=seo_ov if isinstance(seo_ov, dict) else None)
        db.commit()
        db.refresh(job)
        logger.info("job created id=%s title=%s", job.id, job.title)
        return _to_detail(job, db)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("create_job failed")
        raise HTTPException(status_code=500, detail="Failed to create job") from None


@router.put("/admin/jobs/{job_id}", response_model=JobDetail)
def update_job(
    job_id: str,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        data = payload.model_dump(exclude_unset=True)
        seo_ov = data.pop("seo", None)
        if seo_ov is not None and not isinstance(seo_ov, dict) and hasattr(seo_ov, "model_dump"):
            seo_ov = seo_ov.model_dump()
        if "title" in data and data["title"]:
            # regenerate slug only if title changes significantly and slug collision-free
            new_slug = _unique_slug(db, data["title"], exclude_id=job.id)
            job.slug = new_slug
        _apply_job_fields(job, data, db, is_create=False)
        upsert_job_seo(
            db, job, seo_override=seo_ov if isinstance(seo_ov, dict) else None
        )
        db.commit()
        db.refresh(job)
        logger.info("job updated id=%s", job.id)
        return _to_detail(job, db)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("update_job failed id=%s", job_id)
        raise HTTPException(status_code=500, detail="Failed to update job") from None


@router.delete("/admin/jobs/{job_id}")
def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        db.query(JobAttachment).filter(JobAttachment.job_id == job_id).delete()
        db.query(JobQnA).filter(JobQnA.job_id == job_id).delete()
        delete_seo(db, "job", job_id)
        db.delete(job)
        db.commit()
        logger.info("job deleted id=%s", job_id)
        return {"ok": True, "id": job_id}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("delete_job failed id=%s", job_id)
        raise HTTPException(status_code=500, detail="Failed to delete job") from None


@router.post("/admin/jobs/{job_id}/fetch-qna", response_model=QnAFetchResult)
def admin_fetch_qna(
    job_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        result = fetch_qna_for_job_title(db, job_id=job.id, job_title=job.title)
        items = [JobQnAOut.model_validate(x) for x in result.get("items") or []]
        return QnAFetchResult(
            items=items,
            count=result.get("count") or 0,
            elapsed_seconds=result.get("elapsed_seconds") or 0,
            error=result.get("error"),
            videos_scanned=result.get("videos_scanned") or 0,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("admin_fetch_qna failed id=%s", job_id)
        return QnAFetchResult(items=[], count=0, elapsed_seconds=0, error=str(exc), videos_scanned=0)


@router.get("/filters", response_model=FiltersResponse)
def get_filters(db: Session = Depends(get_db)):
    try:
        jobs = db.execute(select(Job)).scalars().all()
        tags: list[str] = ["Government", "Private"]
        cities_db: list[str] = []
        # Homepage "Categories" select = defaults + every tag used on job posts
        category_set: set[str] = set(DEFAULT_CATEGORIES)
        companies: list[str] = []
        for j in jobs:
            for t in _list_field(j.tags):
                tags.append(t)
                category_set.add(t)
            for c in _list_field(j.cities):
                cities_db.append(c)
                tags.append(c)
            for s in _list_field(j.skills):
                tags.append(s)
            if j.source:
                companies.append(j.source)

        seen: set[str] = set()
        uniq_tags = []
        for t in tags:
            k = t.lower()
            if k not in seen and t:
                seen.add(k)
                uniq_tags.append(t)

        # Case-insensitive unique categories, preserve nicer casing
        cat_map: dict[str, str] = {}
        for c in category_set:
            if not c or not str(c).strip():
                continue
            key = str(c).strip().lower()
            if key not in cat_map:
                cat_map[key] = str(c).strip()
        categories = sorted(cat_map.values(), key=str.lower)

        cities = sorted(set(PAKISTAN_CITIES) | set(cities_db), key=str.lower)
        return FiltersResponse(
            source_types=["govt", "private"],
            sectors=SECTORS,
            categories=categories,
            cities=cities,
            companies=sorted(set(companies)),
            employment_types=[],
            tags=uniq_tags[:200],
            job_types=JOB_TYPES,
        )
    except Exception:
        logger.exception("get_filters failed")
        data = empty_filters()
        data["cities"] = PAKISTAN_CITIES
        data["categories"] = DEFAULT_CATEGORIES
        return FiltersResponse(**data)
