from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import empty_stats
from app.logging_config import get_logger
from app.models import Job
from app.schemas import StatsResponse
from app.utils import as_list

router = APIRouter()
logger = get_logger("jobportal.stats")


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    try:
        by_job_type: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_city: dict[str, int] = {}
        by_category: dict[str, int] = {}

        open_for_apply = 0
        archived_jobs = 0
        active_government_jobs = 0
        active_private_jobs = 0
        pakistan_today = datetime.now(ZoneInfo("Asia/Karachi")).date()

        jobs = db.execute(
            select(
                Job.deadline_date,
                Job.job_type,
                Job.cities,
                Job.tags,
                Job.updated_at,
            )
        ).all()
        total = len(jobs)
        for j in jobs:
            archived = bool(
                j.deadline_date and j.deadline_date.date() < pakistan_today
            )
            if archived:
                archived_jobs += 1
            else:
                open_for_apply += 1

            jt = (j.job_type or "private").lower()
            if jt in {"govt", "government", "gov"}:
                key = "govt"
                if not archived:
                    active_government_jobs += 1
            else:
                key = "private"
                if not archived:
                    active_private_jobs += 1
            by_job_type[jt if jt in {"government", "private"} else key] = (
                by_job_type.get(jt if jt in {"government", "private"} else key, 0) + 1
            )
            by_source[key] = by_source.get(key, 0) + 1
            for c in as_list(j.cities):
                by_city[c] = by_city.get(c, 0) + 1
            for t in as_list(j.tags)[:1]:
                by_category[t] = by_category.get(t, 0) + 1

        last = max((job.updated_at for job in jobs if job.updated_at), default=None)
        logger.info("stats total_jobs=%s open_for_apply=%s", total, open_for_apply)
        return StatsResponse(
            total_jobs=total,
            open_for_apply=open_for_apply,
            archived_jobs=archived_jobs,
            active_government_jobs=active_government_jobs,
            active_private_jobs=active_private_jobs,
            by_source_type=by_source,
            by_category=dict(sorted(by_category.items(), key=lambda x: -x[1])[:15]),
            by_city=dict(sorted(by_city.items(), key=lambda x: -x[1])[:15]),
            by_job_type=by_job_type,
            last_updated=last,
        )
    except Exception:
        logger.exception("get_stats failed")
        return StatsResponse(**empty_stats())
