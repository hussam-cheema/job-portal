#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time

import httpx

from common import admin_headers, api_base, require_response, run


def check() -> str:
    parser = argparse.ArgumentParser(description="Submit and verify a contact form message.")
    parser.add_argument("--keep", action="store_true", help="Keep the submitted message in PostgreSQL.")
    parser.add_argument("--email", default=None)
    args = parser.parse_args()

    stamp = int(time.time() * 1000)
    payload = {
        "name": "Contact API Diagnostic",
        "email": args.email or f"jobportal.qa+{stamp}@gmail.com",
        "subject": "Automated contact form check",
        "message": f"Contact form diagnostic message {stamp}.",
    }
    with httpx.Client(timeout=20.0) as client:
        response = client.post(f"{api_base()}/api/contact", json=payload)
        require_response(response, "contact form submission")
        message = response.json()
        message_id = message.get("id")
        if not message_id or message.get("email") != payload["email"].lower():
            raise RuntimeError("contact response did not match the submitted message")

        cleanup = "kept"
        if not args.keep:
            try:
                headers = admin_headers(client)
                require_response(
                    client.delete(f"{api_base()}/api/admin/contact/{message_id}", headers=headers),
                    "contact test cleanup",
                )
                cleanup = "deleted after verification"
            except Exception as exc:
                cleanup = f"kept because cleanup failed: {exc}"
    return f"contact message {message_id} was accepted and {cleanup}"


if __name__ == "__main__":
    raise SystemExit(run(check))
