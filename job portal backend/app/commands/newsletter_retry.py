from __future__ import annotations

from app.database import SessionLocal
from app.logging_config import get_logger, setup_logging
from app.services.newsletter import process_pending_job_alerts

logger = get_logger("jobportal.commands.newsletter_retry")


def run() -> dict[str, object]:
    """Process one bounded batch and exit so a serverless cron can stop."""
    db = SessionLocal()
    try:
        result = process_pending_job_alerts(db, max_deliveries=1000)
        logger.info(
            "newsletter retry batch processed=%s delivered=%s",
            result["processed_count"],
            result["delivered_count"],
        )
        return result
    except Exception:
        db.rollback()
        logger.exception("newsletter retry batch failed")
        raise
    finally:
        db.close()


def main() -> int:
    setup_logging()
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
