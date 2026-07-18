from __future__ import annotations

import argparse

import httpx

from common import CheckFailed, add_backend_to_path, admin_headers, api_base, require_response, run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test the event-driven job-alert subscription API.")
    parser.add_argument("--email", default="pakjobs.manual.subscription.test@gmail.com")
    parser.add_argument(
        "--send-test-email",
        action="store_true",
        help="Send the latest job only to --email using the configured local SMTP account.",
    )
    return parser.parse_args()


def check() -> str:
    args = parse_args()
    email = args.email.strip().lower()
    with httpx.Client(timeout=20) as client:
        invalid = client.post(f"{api_base()}/api/subscriptions", json={"email": "not-an-email"})
        if invalid.status_code not in {400, 422}:
            raise CheckFailed("invalid email was unexpectedly accepted")
        first = require_response(client.post(f"{api_base()}/api/subscriptions", json={"email": email}), "first subscription").json()
        if first.get("status") not in {"subscribed", "already_subscribed"}:
            raise CheckFailed(f"unexpected first status: {first}")
        duplicate = require_response(client.post(f"{api_base()}/api/subscriptions", json={"email": email.upper()}), "duplicate subscription").json()
        if duplicate.get("status") != "already_subscribed":
            raise CheckFailed(f"duplicate was not detected: {duplicate}")
        summary = require_response(client.get(f"{api_base()}/api/admin/subscriptions", headers=admin_headers(client)), "admin subscription summary").json()
        if summary.get("active_subscriber_count", 0) < 1:
            raise CheckFailed("admin summary did not count the active subscription")
        if not summary.get("subject_template") or not summary.get("body_template"):
            raise CheckFailed("digest templates were not returned")
        delivery_status = "test email not requested"
    if args.send_test_email:
        add_backend_to_path()
        from sqlalchemy import select

        from app.database import SessionLocal
        from app.models import EmailSubscriber, Job
        from app.services.newsletter import build_job_alert_message, _send_smtp_message

        with SessionLocal() as db:
            subscriber = db.execute(
                select(EmailSubscriber).where(EmailSubscriber.subscribed_email == email)
            ).scalar_one_or_none()
            job = db.execute(
                select(Job).order_by(Job.created_at.desc())
            ).scalars().first()
            if not subscriber:
                raise CheckFailed(f"subscriber {email} was not found in the configured database")
            if not job:
                raise CheckFailed("create at least one job before sending a test alert")
            _send_smtp_message(build_job_alert_message(db, subscriber, job))
            delivery_status = f"latest-job test email sent for {job.title!r}"
    return f"validation, subscription, duplicate handling, template, and count passed ({email}; {delivery_status})"


if __name__ == "__main__":
    raise SystemExit(run(check))
