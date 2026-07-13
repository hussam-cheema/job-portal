#!/usr/bin/env python3
from __future__ import annotations

import argparse
import uuid

import httpx

from common import CheckFailed, add_backend_to_path, api_base, env, require_response, run


def check() -> str:
    parser = argparse.ArgumentParser(description="Test R2 upload under a specific job post ID.")
    parser.add_argument("job_id", nargs="?", default=env("TEST_JOB_POST_ID"))
    parser.add_argument("--keep", action="store_true", help="Do not delete the test object after verification.")
    args = parser.parse_args()

    with httpx.Client(timeout=20.0) as client:
        if not args.job_id:
            jobs_response = client.get(f"{api_base()}/api/jobs", params={"page": 1, "page_size": 1})
            require_response(jobs_response, "first job lookup")
            jobs = jobs_response.json().get("items") or []
            if not jobs or not jobs[0].get("id"):
                raise CheckFailed("the PostgreSQL jobs table contains no job posts")
            args.job_id = jobs[0]["id"]
            print(f"[INFO] using first listed job post ID: {args.job_id}", flush=True)
        job_response = client.get(f"{api_base()}/api/jobs/{args.job_id}")
    require_response(job_response, f"job lookup for {args.job_id}")

    add_backend_to_path()
    from app.services import storage

    marker = f"job-portal-r2-check:{args.job_id}:{uuid.uuid4().hex}".encode()
    uploaded = storage.upload_bytes(
        marker,
        filename="r2-diagnostic.txt",
        content_type="text/plain",
        folder="attachments",
        job_id=args.job_id,
    )
    key = uploaded["s3_path"]
    expected_segment = f"/{args.job_id}/attachments/"
    if expected_segment not in f"/{key}":
        raise CheckFailed(f"R2 key is not scoped to the requested job: {key}")

    client = storage._r2_client()
    bucket = storage._bucket()
    try:
        body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
        if body != marker:
            raise CheckFailed("downloaded R2 object content did not match the uploaded bytes")
    finally:
        if not args.keep:
            client.delete_object(Bucket=bucket, Key=key)
    cleanup = "kept" if args.keep else "deleted after verification"
    return f"R2 upload verified in {bucket}/{key} ({cleanup})"


if __name__ == "__main__":
    raise SystemExit(run(check))
