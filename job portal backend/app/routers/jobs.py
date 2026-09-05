from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import cast, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.types import String

from app.auth import get_current_admin
from app.constants import (
    DEFAULT_CATEGORIES,
    JOB_TYPES,
    PAKISTAN_ALL_CITIES,
    PAKISTAN_CITIES,
    PAKISTAN_CITIES_BY_PROVINCE,
    PAKISTAN_NEWSPAPERS,
    PAKISTAN_PROVINCE_BY_CITY,
    PAKISTAN_PROVINCES,
    SECTORS,
)
from app.database import get_db
from app.exceptions import empty_filters, empty_job_list
from app.logging_config import get_logger
from app.models import Job, JobAttachment, JobQnA, TaxonomyTerm, User
from app.schemas import (
    FiltersResponse,
    JobCreate,
    JobDetail,
    JobListResponse,
    JobQnAOut,
    JobSummary,
    JobUpdate,
    QnAFetchOptions,
    QnAFetchResult,
)
from app.services.qna import fetch_qna_for_job_title, is_acceptable_qna_answer
from app.services.directory_pages import ensure_job_directory_pages
from app.services.newsletter import process_pending_job_alerts, queue_new_job_alert
from app.services.seo import delete_seo, upsert_job_seo
from app.services.storage import delete_objects
from app.services.watermark import process_description_images
from app.services.taxonomy import (
    canonicalize_job_locations,
    canonicalize_job_terms,
    ensure_default_taxonomy,
)
from app.services.job_data_quality import (
    canonicalize_job_organization,
    clean_optional_list,
    clean_optional_text,
)
from app.utils import as_list, experience_label, normalize_job_type, slugify

router = APIRouter()
logger = get_logger("jobportal.jobs")

# List cards do not need the complete rich-text description or ORM bookkeeping
# columns. Returning a bounded preview substantially reduces Neon row transfer;
# the detail endpoint remains the source for the complete job record.
JOB_SUMMARY_COLUMNS = (
    Job.id,
    Job.slug,
    Job.title,
    func.substr(Job.description, 1, 1600).label("description"),
    Job.published_date,
    Job.deadline_date,
    Job.salary_range,
    Job.source,
    Job.newspaper,
    Job.reference_url,
    Job.application_url,
    Job.experience_required,
    Job.education_required,
    Job.skills,
    Job.job_type,
    Job.cities,
    Job.provinces,
    Job.tags,
    Job.keywords,
    Job.created_at,
)


def _list_field(value) -> list[str]:
    return as_list(value)


def _source_type(job: Any) -> str:
    jt = (job.job_type or "").lower()
    if jt in {"government", "govt", "gov"}:
        return "govt"
    return "private"


def _to_summary(job: Any) -> JobSummary:
    cities = _list_field(job.cities)
    provinces = _list_field(job.provinces)
    tags = _list_field(job.tags)
    skills = _list_field(job.skills)
    configured_cities = {city.casefold() for city in PAKISTAN_CITIES}
    selected_cities = {city.casefold() for city in cities}
    nationwide = (
        PAKISTAN_ALL_CITIES.casefold() in selected_cities
        or (bool(configured_cities) and configured_cities.issubset(selected_cities))
        or (
            len(selected_cities) >= 20
            and len(selected_cities & configured_cities) / len(configured_cities) >= 0.9
        )
    )
    locations = [*provinces, *cities]
    location = "Pakistan" if nationwide else ", ".join(locations) if locations else None
    deadline = job.deadline_date
    applications_closed = bool(
        deadline and deadline.date() < datetime.now(ZoneInfo("Asia/Karachi")).date()
    )

    return JobSummary(
        id=job.id,
        slug=job.slug,
        title=job.title,
        description=job.description,
        published_date=job.published_date,
        deadline_date=job.deadline_date,
        salary_range=job.salary_range,
        source=job.source,
        newspaper=job.newspaper,
        reference_url=job.reference_url,
        application_url=job.application_url,
        experience_required=job.experience_required,
        education_required=job.education_required,
        skills=skills,
        job_type=job.job_type,
        cities=cities,
        provinces=provinces,
        tags=tags,
        keywords=job.keywords,
        created_at=job.created_at,
        company=job.source,
        location=location,
        city="Pakistan" if nationwide else cities[0] if cities else None,
        province=provinces[0] if provinces else None,
        employment_type=None,
        salary_min=None,
        salary_max=None,
        currency="PKR",
        category=tags[0] if tags else None,
        application_deadline=job.deadline_date,
        source_type=_source_type(job),
        source_name=job.source,
        nationwide=nationwide,
        applications_closed=applications_closed,
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
                select(JobQnA)
                .where(JobQnA.job_id == job.id)
                .order_by(JobQnA.created_at.asc())
            )
            .scalars()
            .all()
        )
        qna = [row for row in qna if is_acceptable_qna_answer(row.question, row.answer)]
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
        q = select(Job.id).where(Job.slug == candidate)
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
            job.slug = _unique_slug(
                db, job.title, exclude_id=None if is_create else job.id
            )
        elif data.get("title"):
            # keep slug stable on update unless empty
            pass
    if "description" in data and data["description"] is not None:
        try:
            job.description = process_description_images(data["description"], job.id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if "published_date" in data and data["published_date"] is not None:
        job.published_date = data["published_date"]
    if "deadline_date" in data:
        job.deadline_date = data["deadline_date"]
    if "salary_range" in data:
        job.salary_range = clean_optional_text(data["salary_range"])
    if "source" in data:
        job.source = canonicalize_job_organization(db, data["source"])
    if "newspaper" in data:
        job.newspaper = clean_optional_text(data["newspaper"])
    if "reference_url" in data:
        job.reference_url = clean_optional_text(data["reference_url"])
    if "application_url" in data:
        job.application_url = clean_optional_text(data["application_url"])
    if "experience_required" in data:
        job.experience_required = experience_label(
            clean_optional_text(data["experience_required"])
        )
    if "education_required" in data:
        job.education_required = clean_optional_text(data["education_required"])
    if "skills" in data:
        job.skills = clean_optional_list(data["skills"])
    if "job_type" in data:
        job.job_type = normalize_job_type(clean_optional_text(data["job_type"]))
    if is_create or "cities" in data or "provinces" in data:
        selected_cities = (
            as_list(data.get("cities"))
            if "cities" in data
            else as_list(job.cities)
        )
        selected_provinces = (
            as_list(data.get("provinces"))
            if "provinces" in data
            else as_list(job.provinces)
        )
        # Replacing a country-wide marker with a province must not retain the
        # previous Pakistan city marker.
        if "provinces" in data and "cities" not in data and any(
            value.casefold() == PAKISTAN_ALL_CITIES.casefold()
            for value in selected_cities
        ):
            selected_cities = []
        job.cities, canonical_provinces = canonicalize_job_locations(
            db, selected_cities, selected_provinces
        )
        job.provinces = canonical_provinces or None
    if "tags" in data:
        selected_tags = clean_optional_list(data["tags"])
        job.tags = canonicalize_job_terms(db, selected_tags) if selected_tags else None
    if "keywords" in data:
        job.keywords = clean_optional_text(data["keywords"])
    job.updated_at = datetime.utcnow()


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    q: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    newspaper: Optional[str] = Query(None),
    education: Optional[str] = Query(None),
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

        stmt = select(*JOB_SUMMARY_COLUMNS)
        count_stmt = select(func.count()).select_from(Job)
        filters = []

        if q:
            like = f"%{q.strip()}%"
            filters.append(
                or_(
                    Job.title.ilike(like),
                    Job.description.ilike(like),
                    Job.source.ilike(like),
                    Job.newspaper.ilike(like),
                    Job.keywords.ilike(like),
                    cast(Job.skills, String).ilike(like),
                    cast(Job.tags, String).ilike(like),
                    cast(Job.cities, String).ilike(like),
                    cast(Job.provinces, String).ilike(like),
                )
            )
        if source_type or sector or job_type:
            raw = (job_type or sector or source_type or "").lower().strip()
            if raw in {"govt", "government", "gov"}:
                filters.append(Job.job_type.in_(["government", "govt", "gov"]))
            elif raw in {"private", "company", "newspaper"}:
                filters.append(
                    or_(
                        Job.job_type.in_(["private", "company", "newspaper"]),
                        Job.job_type.is_(None),
                    )
                )
        if category:
            like = f"%{category.strip()}%"
            filters.append(cast(Job.tags, String).ilike(like))
        if city:
            requested_city = city.strip()
            canonical_city = next(
                (
                    value
                    for value in PAKISTAN_CITIES
                    if value.casefold() == requested_city.casefold()
                ),
                requested_city,
            )
            # A city landing page must contain only jobs explicitly assigned to
            # that city. Province-wide jobs remain available on the province
            # page and must not be duplicated across every city in that province.
            filters.append(
                func.lower(cast(Job.cities, String)).like(
                    f'%"{canonical_city.casefold()}"%'
                )
            )
        if province:
            requested_province = province.strip()
            canonical_province = next(
                (
                    value
                    for value in PAKISTAN_PROVINCES
                    if value.casefold() == requested_province.casefold()
                ),
                requested_province,
            )
            province_filters = [
                func.lower(cast(Job.provinces, String)).like(
                    f'%"{canonical_province.casefold()}"%'
                ),
            ]
            linked_cities = list(PAKISTAN_CITIES_BY_PROVINCE.get(canonical_province, []))
            linked_cities.extend(
                row.name
                for row in db.execute(
                    select(TaxonomyTerm).where(
                        TaxonomyTerm.kind == "city",
                        TaxonomyTerm.province == canonical_province,
                    )
                ).scalars()
                if row.name not in linked_cities
            )
            province_filters.extend(
                func.lower(cast(Job.cities, String)).like(
                    f'%"{linked_city.casefold()}"%'
                )
                for linked_city in linked_cities
            )
            filters.append(or_(*province_filters))
        if company:
            filters.append(func.lower(Job.source) == company.strip().casefold())
        if newspaper:
            filters.append(
                func.lower(Job.newspaper) == newspaper.strip().casefold()
            )
        if education:
            filters.append(Job.education_required.ilike(f"%{education.strip()}%"))
        if tag:
            t = tag.strip()
            t_lower = t.lower()
            if t_lower in {"government", "govt"}:
                filters.append(Job.job_type.in_(["government", "govt", "gov"]))
            elif t_lower == "private":
                filters.append(
                    or_(
                        Job.job_type.in_(["private", "company"]), Job.job_type.is_(None)
                    )
                )
            else:
                like = f"%{t}%"
                filters.append(
                    or_(
                        cast(Job.tags, String).ilike(like),
                        cast(Job.skills, String).ilike(like),
                        cast(Job.cities, String).ilike(like),
                        cast(Job.provinces, String).ilike(like),
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
        rows = db.execute(
            stmt.order_by(Job.published_date.desc().nullslast(), Job.created_at.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
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
        job = db.execute(
            select(Job).where(or_(Job.id == job_id, Job.slug == job_id)).limit(1)
        ).scalar_one_or_none()
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


@router.get("/admin/jobs", response_model=JobListResponse)
def admin_list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """Return every editable job through a bounded, admin-only listing."""
    try:
        total = db.execute(select(func.count()).select_from(Job)).scalar() or 0
        pages = math.ceil(total / page_size) if total else 0
        rows = db.execute(
            select(*JOB_SUMMARY_COLUMNS)
            .order_by(Job.published_date.desc().nullslast(), Job.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return JobListResponse(
            items=[_to_summary(job) for job in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )
    except Exception:
        logger.exception("admin_list_jobs failed page=%s", page)
        raise HTTPException(status_code=503, detail="Failed to load job posts") from None


@router.post("/admin/jobs", response_model=JobDetail)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        if not payload.title or not payload.description or not payload.published_date:
            raise HTTPException(
                status_code=400, detail="title, description, published_date required"
            )
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
        ensure_job_directory_pages(db, job)
        upsert_job_seo(
            db, job, seo_override=seo_ov if isinstance(seo_ov, dict) else None
        )
        # Atomically publish the job and stage exactly one delivery for every
        # subscriber. There is no post-commit gap in which a published job can
        # exist without its newsletter outbox.
        alert_run = queue_new_job_alert(db, job)
        db.commit()
        db.refresh(job)
        logger.info("job created id=%s title=%s", job.id, job.title)
        # The first delivery attempt runs during the publish request. Automatic
        # retries remain a safety net for failures outside the application's
        # control after every intended recipient has already been persisted.
        try:
            if alert_run.recipients_count:
                process_pending_job_alerts(
                    db,
                    job_id=job.id,
                    max_deliveries=alert_run.recipients_count,
                )
            db.refresh(alert_run)
            logger.info(
                "new job alert processed job_id=%s status=%s sent=%s failed=%s",
                job.id,
                alert_run.status,
                alert_run.sent_count,
                alert_run.failed_count,
            )
        except Exception:
            db.rollback()
            logger.exception(
                "new job alert processing failed after commit job_id=%s", job.id
            )
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
        if (
            seo_ov is not None
            and not isinstance(seo_ov, dict)
            and hasattr(seo_ov, "model_dump")
        ):
            seo_ov = seo_ov.model_dump()
        # A published job URL is permanent. Editing a title must never mutate
        # the canonical slug and invalidate links already indexed or shared.
        _apply_job_fields(job, data, db, is_create=False)
        directory_fields = {"source", "newspaper", "tags", "cities", "provinces"}
        if directory_fields.intersection(data):
            ensure_job_directory_pages(db, job)
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
        attachment_keys = (
            db.execute(
                select(JobAttachment.s3_path).where(JobAttachment.job_id == job_id)
            )
            .scalars()
            .all()
        )
        delete_objects(list(attachment_keys))
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
    options: Optional[QnAFetchOptions] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    try:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        result = fetch_qna_for_job_title(
            db,
            job_id=job.id,
            job_title=job.title,
            min_similarity_percent=(
                options.min_similarity_percent if options is not None else None
            ),
            youtube_video_count=(
                options.max_youtube_videos if options is not None else None
            ),
            comments_per_video=(options.max_comments if options is not None else None),
        )
        items = [JobQnAOut.model_validate(x) for x in result.get("items") or []]
        return QnAFetchResult(
            items=items,
            count=result.get("count") or 0,
            elapsed_seconds=result.get("elapsed_seconds") or 0,
            error=result.get("error"),
            videos_compared=result.get("videos_compared") or 0,
            videos_scanned=result.get("videos_scanned") or 0,
            matched_videos=result.get("matched_videos") or [],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("admin_fetch_qna failed id=%s", job_id)
        return QnAFetchResult(
            items=[],
            count=0,
            elapsed_seconds=0,
            error=str(exc),
            videos_compared=0,
            videos_scanned=0,
            matched_videos=[],
        )


@router.get("/filters", response_model=FiltersResponse)
def get_filters(db: Session = Depends(get_db)):
    try:
        ensure_default_taxonomy(db)
        category_set: set[str] = {
            row.name
            for row in db.execute(
                select(TaxonomyTerm).where(
                    TaxonomyTerm.kind == "category",
                    TaxonomyTerm.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        }
        city_set: set[str] = {
            row.name
            for row in db.execute(
                select(TaxonomyTerm).where(
                    TaxonomyTerm.kind == "city",
                    TaxonomyTerm.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        }
        companies: list[str] = []
        newspapers: list[str] = list(PAKISTAN_NEWSPAPERS)
        qualifications: list[str] = []
        jobs = db.execute(
            select(Job.source, Job.newspaper, Job.education_required)
        ).all()
        for source, newspaper, education_required in jobs:
            if source:
                companies.append(source.strip())
            if newspaper:
                newspapers.append(newspaper.strip())
            if education_required:
                qualifications.append(education_required.strip())

        # Case-insensitive unique categories, preserve nicer casing
        cat_map: dict[str, str] = {}
        for c in category_set:
            if not c or not str(c).strip():
                continue
            key = str(c).strip().lower()
            if key not in cat_map:
                cat_map[key] = str(c).strip()
        categories = sorted(cat_map.values(), key=str.lower)

        cities = sorted(city_set, key=str.casefold)
        return FiltersResponse(
            source_types=["govt", "private"],
            sectors=SECTORS,
            categories=categories,
            cities=cities,
            provinces=PAKISTAN_PROVINCES,
            companies=sorted(set(filter(None, companies)), key=str.casefold),
            newspapers=sorted(set(filter(None, newspapers)), key=str.casefold),
            employment_types=[],
            # Kept for backwards-compatible clients; tags now represent only
            # the controlled category taxonomy, not cities or free-form skills.
            tags=categories,
            job_types=JOB_TYPES,
            qualifications=sorted(set(filter(None, qualifications)), key=str.lower),
        )
    except Exception:
        logger.exception("get_filters failed")
        data = empty_filters()
        data["cities"] = [PAKISTAN_ALL_CITIES, *PAKISTAN_CITIES]
        data["provinces"] = PAKISTAN_PROVINCES
        data["categories"] = DEFAULT_CATEGORIES
        return FiltersResponse(**data)
