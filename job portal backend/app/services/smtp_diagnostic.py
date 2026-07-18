from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

from sqlalchemy import select

from app.database import SessionLocal
from app.models import EmailSubscriber
from app.services.smtp_transport import (
    deliver_smtp_message,
    load_smtp_settings,
    masked_address,
)


def _active_subscriber() -> str:
    with SessionLocal() as db:
        subscriber = db.execute(
            select(EmailSubscriber)
            .where(EmailSubscriber.is_active.is_(True))
            .order_by(EmailSubscriber.subscribed_at.asc())
        ).scalars().first()
        if not subscriber:
            raise RuntimeError("No active subscriber was found in the configured database")
        return subscriber.subscribed_email


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Test SMTP config, DNS, TLS, authentication, recipient acceptance, "
            "and final server acceptance without printing the password."
        )
    )
    parser.add_argument(
        "--recipient",
        help="Destination address. By default, use the oldest active database subscriber.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Required safety flag because the diagnostic sends one labeled email.",
    )
    args = parser.parse_args()
    if not args.send:
        parser.error("Pass --send to confirm that one diagnostic email may be sent")

    recipient = (args.recipient or _active_subscriber()).strip().lower()
    settings = load_smtp_settings()
    now = datetime.now(timezone.utc)
    message = EmailMessage()
    message["Subject"] = f"PakistanJobs SMTP diagnostic — {now.isoformat()}"
    message["From"] = settings.from_email
    message["To"] = recipient
    message["Date"] = format_datetime(now)
    message["Message-ID"] = make_msgid(
        domain=settings.from_email.rpartition("@")[2] or None
    )
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(
        "This message was sent by the PakistanJobs production SMTP diagnostic.\n\n"
        "If it is not in Inbox, check Spam, All Mail, filters, blocked senders, and "
        "the sender account for a bounce notice."
    )

    print(f"Diagnostic recipient: {masked_address(recipient)}")

    def report(stage: str, detail: str) -> None:
        print(f"[PASS] {stage}: {detail}")

    try:
        receipt = deliver_smtp_message(message, reporter=report)
    except Exception as exc:
        code = getattr(exc, "smtp_code", None)
        error = getattr(exc, "smtp_error", None)
        suffix = f" (SMTP {code}: {error!r})" if code is not None else ""
        print(f"[FAIL] {type(exc).__name__}: {exc}{suffix}", file=sys.stderr)
        return 1

    print(
        f"[PASS] accepted: message_id={receipt.message_id}; "
        f"smtp_code={receipt.response_code}; response={receipt.response}"
    )
    print(
        "[INFO] SMTP acceptance proves the password and application transport are valid; "
        "it does not prove Inbox placement by the recipient provider."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
