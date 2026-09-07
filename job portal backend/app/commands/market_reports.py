"""Publish due monthly reports; safe to run repeatedly or concurrently."""

from app.database import SessionLocal
from app.logging_config import get_logger, setup_logging
from app.services.market_reports import publish_due_reports

logger = get_logger("jobportal.market_reports")


def run() -> list[str]:
    with SessionLocal() as db:
        created = publish_due_reports(db)
        if created:
            logger.info("Published monthly market reports: %s", ", ".join(created))
        return created


def main() -> int:
    setup_logging()
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
