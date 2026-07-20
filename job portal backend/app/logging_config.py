from __future__ import annotations

import logging
import os
import sys
from typing import Optional

from app.r2_logging import R2ProductionLogHandler, r2_production_logging_enabled


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if not any(getattr(handler, "_jobportal_console", False) for handler in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler._jobportal_console = True  # type: ignore[attr-defined]
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if (
        r2_production_logging_enabled()
        and not any(isinstance(handler, R2ProductionLogHandler) for handler in root.handlers)
    ):
        required = (
            "R2_ACCOUNT_ID",
            "R2_ACCESS_KEY_ID",
            "R2_SECRET_ACCESS_KEY",
            "R2_BUCKET_NAME",
        )
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise RuntimeError(
                "R2 production logging is enabled but missing: " + ", ".join(missing)
            )
        root.addHandler(R2ProductionLogHandler())

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or "jobportal")


def flush_production_logs() -> None:
    for handler in logging.getLogger().handlers:
        if isinstance(handler, R2ProductionLogHandler):
            handler.flush()
