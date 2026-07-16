from __future__ import annotations

import argparse

import httpx

from common import CheckFailed, admin_headers, api_base, require_response, run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test the daily job-alert subscription API.")
    parser.add_argument("--email", default="pakjobs.manual.subscription.test@gmail.com")
    parser.add_argument(
        "--send-digest",
        action="store_true",
        help="Explicitly process the current digest window using the configured SMTP account.",
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
        digest_status = "not sent"
        if args.send_digest:
            digest = require_response(
                client.post(
                    f"{api_base()}/api/admin/subscriptions/send-digest",
                    headers=admin_headers(client),
                ),
                "manual digest",
            ).json()
            digest_status = f"digest status={digest.get('status')}, sent={digest.get('sent_count', 0)}"
    return f"validation, subscription, duplicate handling, template, and count passed ({email}; {digest_status})"


if __name__ == "__main__":
    raise SystemExit(run(check))
