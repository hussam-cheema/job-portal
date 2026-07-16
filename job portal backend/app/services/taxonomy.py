from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import DEFAULT_CATEGORIES
from app.models import Job, SiteSetting, TaxonomyTerm
from app.utils import as_list, slugify


def ensure_default_taxonomy(db: Session) -> list[TaxonomyTerm]:
    """Seed built-in and legacy job categories without overwriting admin edits."""
    existing = db.execute(select(TaxonomyTerm)).scalars().all()
    known_slugs = {(row.kind, row.slug.lower()) for row in existing}
    marker_key = "taxonomy_defaults_seeded_v1"
    marker = db.get(SiteSetting, marker_key)
    names: list[str] = list(DEFAULT_CATEGORIES) if marker is None else []
    for job in db.execute(select(Job)).scalars().all():
        names.extend(as_list(job.tags))

    created: list[TaxonomyTerm] = []
    for raw in names:
        name = str(raw).strip()
        slug = slugify(name)
        key = ("category", slug.lower())
        if not name or not slug or key in known_slugs:
            continue
        row = TaxonomyTerm(
            id=str(uuid4()),
            kind="category",
            name=name,
            slug=slug,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        created.append(row)
        known_slugs.add(key)
    if created:
        db.flush()
    if marker is None:
        db.add(
            SiteSetting(
                key=marker_key,
                value="true",
                updated_at=datetime.utcnow(),
            )
        )
        db.flush()
    return created


def canonicalize_job_terms(db: Session, values: list[str]) -> list[str]:
    ensure_default_taxonomy(db)
    rows = (
        db.execute(
            select(TaxonomyTerm).where(
                TaxonomyTerm.kind == "category",
            )
        )
        .scalars()
        .all()
    )
    by_name = {row.name.strip().lower(): row.name for row in rows}
    by_slug = {row.slug.strip().lower(): row.name for row in rows}
    result: list[str] = []
    seen: set[str] = set()
    unknown: list[str] = []
    for raw in values:
        clean = str(raw).strip()
        if not clean:
            continue
        canonical = by_name.get(clean.lower()) or by_slug.get(slugify(clean).lower())
        if not canonical:
            unknown.append(clean)
            continue
        key = canonical.lower()
        if key not in seen:
            seen.add(key)
            result.append(canonical)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                "Select only predefined tags/categories. Unknown: "
                + ", ".join(unknown[:10])
            ),
        )
    return result
