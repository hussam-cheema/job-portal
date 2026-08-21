from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Page
from app.page_types import DIRECTORY_PAGE_PATHS, page_slug_namespace
from app.services.seo import upsert_page_seo
from app.utils import as_list, slugify


def _canonical_values(values: Iterable[Any]) -> list[str]:
    """Return stable, case-insensitive directory values with display casing intact."""
    canonical: dict[str, str] = {}
    for raw_value in values:
        value = str(raw_value or "").strip()
        if value and slugify(value):
            canonical.setdefault(value.casefold(), value)
    return sorted(canonical.values(), key=str.casefold)


def _page_copy(page_type: str, value: str) -> tuple[str, str, dict[str, str]]:
    if page_type in {"city", "province", "newspaper"}:
        title = f"Jobs in {value}"
    else:
        title = value if value.casefold().endswith(" jobs") else f"{value} Jobs"
    subject = {
        "city": f"job opportunities in {value}",
        "province": f"job opportunities across {value}",
        "category": f"{value} job opportunities in Pakistan",
        "organization": f"current vacancies from {value}",
        "newspaper": f"job advertisements published in {value}",
    }[page_type]
    content = f"<p>Browse current {subject}.</p>"
    seo = {
        "focus_keyword": title,
        "meta_title": f"{title} | Pakistan Jobs Market",
        "meta_description": f"Browse current {subject} on Pakistan Jobs Market.",
        "meta_keywords": f"{title}, Pakistan jobs, latest jobs in Pakistan",
    }
    return title, content, seo


def ensure_directory_pages(
    db: Session, values_by_type: dict[str, Iterable[Any]]
) -> list[Page]:
    """Create missing CMS Pages for directory values without altering existing Pages.

    All existing Pages are loaded in one query so a job containing several tags and
    locations does not produce an N+1 lookup pattern.
    """
    normalized_values = {
        page_type: _canonical_values(values)
        for page_type, values in values_by_type.items()
        if page_type in DIRECTORY_PAGE_PATHS
    }
    if not any(normalized_values.values()):
        return []

    existing_pages = db.execute(
        select(Page.page_type, Page.taxonomy_value, Page.slug)
    ).all()
    existing_keys = {
        (page.page_type, (page.taxonomy_value or "").strip().casefold())
        for page in existing_pages
        if page.page_type in DIRECTORY_PAGE_PATHS and page.taxonomy_value
    }
    used_slugs = {
        (page_slug_namespace(page.page_type), page.slug.casefold())
        for page in existing_pages
    }
    created: list[Page] = []

    def available_slug(value: str, page_type: str) -> str:
        base = slugify(value) or page_type
        candidate = base
        suffix = 1
        namespace = page_slug_namespace(page_type)
        while (namespace, candidate.casefold()) in used_slugs:
            suffix += 1
            candidate = (
                f"{base}-{page_type}"
                if suffix == 2
                else f"{base}-{page_type}-{suffix}"
            )
        used_slugs.add((namespace, candidate.casefold()))
        return candidate

    for page_type, values in normalized_values.items():
        for value in values:
            key = (page_type, value.casefold())
            if key in existing_keys:
                continue
            title, content, seo = _page_copy(page_type, value)
            page = Page(
                id=str(uuid4()),
                slug=available_slug(value, page_type),
                title=title,
                content=content,
                page_type=page_type,
                taxonomy_value=value,
                is_published=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(page)
            upsert_page_seo(db, page, seo_override=seo)
            created.append(page)
            existing_keys.add(key)
    return created


def ensure_job_directory_pages(db: Session, job: Any) -> list[Page]:
    """Synchronize every directory dimension represented by a saved job."""
    return ensure_directory_pages(
        db,
        {
            "city": as_list(job.cities),
            "province": as_list(job.provinces),
            "category": as_list(job.tags),
            "organization": [job.source],
            "newspaper": [job.newspaper],
        },
    )
