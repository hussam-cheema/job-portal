from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.utils import strip_html

PAKISTAN_TIMEZONE = ZoneInfo("Asia/Karachi")
MIN_INDEXABLE_DESCRIPTION_WORDS = 150


@dataclass(frozen=True)
class JobIndexStatus:
    indexable: bool
    archived: bool
    reasons: tuple[str, ...]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _word_count(value: Any) -> int:
    text = strip_html(str(value or ""))
    return len(re.findall(r"[A-Za-z0-9]+", text))


def _local_date(value: datetime) -> datetime.date:
    if value.tzinfo is None:
        return value.date()
    return value.astimezone(PAKISTAN_TIMEZONE).date()


def job_index_status(
    job: Any,
    *,
    now: datetime | None = None,
) -> JobIndexStatus:
    """Return whether a job record has enough trustworthy information for search.

    Complete closed records remain indexable as archive history. Incomplete or
    thin records stay public for existing links but are excluded from search.
    """
    current = now or datetime.now(PAKISTAN_TIMEZONE)
    reasons: list[str] = []

    deadline = getattr(job, "deadline_date", None)
    archived = bool(deadline and _local_date(deadline) < _local_date(current))
    if deadline is None:
        reasons.append("missing_deadline")

    if not _text(getattr(job, "source", None)):
        reasons.append("missing_source")

    if not (
        _text(getattr(job, "reference_url", None))
        or _text(getattr(job, "application_url", None))
    ):
        reasons.append("missing_source_url")

    if (
        _word_count(getattr(job, "description", None))
        < MIN_INDEXABLE_DESCRIPTION_WORDS
    ):
        reasons.append("thin_description")

    return JobIndexStatus(
        indexable=not reasons,
        archived=archived,
        reasons=tuple(reasons),
    )
