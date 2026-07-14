#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from common import (
    CheckFailed,
    add_backend_to_path,
    admin_headers,
    api_base,
    config,
    require_response,
    run,
)


def _validate_result(result: dict, elapsed: float, configured_limit: float) -> str:
    count = int(result.get("count") or 0)
    error = (result.get("error") or "").strip()
    if elapsed > configured_limit + 5:
        raise CheckFailed(f"Q&A request exceeded its {configured_limit:g}s limit ({elapsed:.2f}s)")
    if count == 0 and not error:
        raise CheckFailed("Q&A returned neither saved pairs nor an explanatory error")
    if count:
        return f"saved {count} Q&A pair(s)"
    return f"returned a visible no-match/error result: {error[:120]}"


def _direct_check(title: str, configured_limit: float) -> str:
    add_backend_to_path()
    from app.database import SessionLocal
    from app.models import Job, JobQnA
    from app.services.qna import fetch_qna_for_job_title

    db = SessionLocal()
    job_id = str(uuid4())
    try:
        db.add(
            Job(
                id=job_id,
                slug=f"qna-integration-{job_id}",
                title=title,
                description="Temporary direct Q&A integration test.",
                published_date=datetime.now(timezone.utc).replace(tzinfo=None),
                cities=["Islamabad"],
                tags=["integration-test"],
                job_type="private",
            )
        )
        db.commit()
        started = time.monotonic()
        result = fetch_qna_for_job_title(db, job_id=job_id, job_title=title)
        elapsed = time.monotonic() - started
        outcome = _validate_result(result, elapsed, configured_limit)
        count = int(result.get("count") or 0)
        if count:
            persisted = db.query(JobQnA).filter(JobQnA.job_id == job_id).count()
            if persisted < count:
                raise CheckFailed("returned Q&A pairs were not persisted to PostgreSQL")
        return f"Q&A pipeline {outcome} and verified PostgreSQL in {elapsed:.2f}s"
    finally:
        db.rollback()
        db.query(JobQnA).filter(JobQnA.job_id == job_id).delete(synchronize_session=False)
        db.query(Job).filter(Job.id == job_id).delete(synchronize_session=False)
        db.commit()
        db.close()


def check() -> str:
    parser = argparse.ArgumentParser(
        description="Create a temporary local job and test the complete YouTube Q&A pipeline."
    )
    parser.add_argument("--title", default="Python Developer")
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Call the service and local PostgreSQL directly instead of authenticating through HTTP.",
    )
    args = parser.parse_args()

    configured_limit = float(config("youtube_qna", "timeout_seconds", default=60) or 60)
    if args.direct:
        return _direct_check(args.title, configured_limit)
    job_id: str | None = None
    with httpx.Client(timeout=configured_limit + 15) as client:
        headers = admin_headers(client)
        try:
            created = client.post(
                f"{api_base()}/api/admin/jobs",
                headers=headers,
                json={
                    "title": f"{args.title} Q&A integration test",
                    "description": "Temporary job created by Scripts/test_qna_pipeline.py.",
                    "published_date": datetime.now(timezone.utc).isoformat(),
                    "job_type": "private",
                    "cities": ["Islamabad"],
                    "tags": ["integration-test"],
                },
            )
            require_response(created, "temporary job creation")
            job_id = created.json().get("id")
            if not job_id:
                raise CheckFailed("temporary job response did not include an id")

            started = time.monotonic()
            response = client.post(
                f"{api_base()}/api/admin/jobs/{job_id}/fetch-qna",
                headers=headers,
            )
            elapsed = time.monotonic() - started
            require_response(response, "YouTube Q&A fetch")
            result = response.json()
            count = int(result.get("count") or 0)
            outcome = _validate_result(result, elapsed, configured_limit)
            if count:
                persisted = client.get(f"{api_base()}/api/jobs/{job_id}")
                require_response(persisted, "temporary job reload")
                saved = persisted.json().get("qna") or []
                if len(saved) < count:
                    raise CheckFailed("returned Q&A pairs were not persisted to PostgreSQL")
                outcome = f"saved and reloaded {count} Q&A pair(s)"
            return f"Q&A pipeline {outcome} through HTTP in {elapsed:.2f}s"
        finally:
            if job_id:
                client.delete(f"{api_base()}/api/admin/jobs/{job_id}", headers=headers)


if __name__ == "__main__":
    raise SystemExit(run(check))
