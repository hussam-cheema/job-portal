from __future__ import annotations

from datetime import datetime

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

        now = datetime.utcnow()
        open_for_apply = 0

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
            # Still open if no deadline, or deadline is in the future (end of day UTC)
            if j.deadline_date is None or j.deadline_date >= now:
                open_for_apply += 1

            jt = (j.job_type or "private").lower()
            if jt in {"govt", "government", "gov"}:
                key = "govt"
            else:
                key = "private"
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
            by_source_type=by_source,
            by_category=dict(sorted(by_category.items(), key=lambda x: -x[1])[:15]),
            by_city=dict(sorted(by_city.items(), key=lambda x: -x[1])[:15]),
            by_job_type=by_job_type,
            last_updated=last,
        )
    except Exception:
        logger.exception("get_stats failed")
        return StatsResponse(**empty_stats())
