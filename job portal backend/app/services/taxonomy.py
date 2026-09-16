from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import (
    DEFAULT_CATEGORIES,
    PAKISTAN_ALL_CITIES,
    PAKISTAN_CITIES,
    PAKISTAN_PROVINCE_BY_CITY,
    PAKISTAN_PROVINCES,
)
from app.models import Job, SiteSetting, TaxonomyTerm
from app.utils import as_list, slugify


def ensure_default_taxonomy(db: Session) -> list[TaxonomyTerm]:
    """Seed real categories and remove legacy city/sector terms once."""
    existing = db.execute(select(TaxonomyTerm)).scalars().all()
    cleanup_marker_key = "taxonomy_reserved_terms_removed_v1"
    cleanup_marker = db.get(SiteSetting, cleanup_marker_key)
    if cleanup_marker is None:
        reserved_slugs = {
            slugify(value).lower()
            for value in [*PAKISTAN_CITIES, "Government", "Private", "Govt"]
        }
        for row in existing:
            if row.kind == "category" and row.slug.lower() in reserved_slugs:
                db.delete(row)
        db.add(
            SiteSetting(
                key=cleanup_marker_key,
                value="true",
                updated_at=datetime.utcnow(),
            )
        )
        db.flush()
        existing = db.execute(select(TaxonomyTerm)).scalars().all()

    known_slugs = {(row.kind, row.slug.lower()) for row in existing}
    marker_key = "taxonomy_defaults_seeded_v1"
    marker = db.get(SiteSetting, marker_key)
    names: list[str] = list(DEFAULT_CATEGORIES) if marker is None else []

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

    # Preserve every location already assigned to a job when moving the editor
    # from the original hard-coded city list to administrator-managed terms.
    city_marker_key = "taxonomy_cities_seeded_v1"
    if db.get(SiteSetting, city_marker_key) is None:
        existing_job_cities = {
            city
            for values in db.execute(select(Job.cities)).scalars().all()
            for city in as_list(values)
            if city
        }
        for raw in sorted(
            {*PAKISTAN_CITIES, PAKISTAN_ALL_CITIES, *existing_job_cities},
            key=str.casefold,
        ):
            name = str(raw).strip()
            slug = slugify(name)
            key = ("city", slug.lower())
            if not name or not slug or key in known_slugs:
                continue
            row = TaxonomyTerm(
                id=str(uuid4()),
                kind="city",
                name=name,
                slug=slug,
                province=PAKISTAN_PROVINCE_BY_CITY.get(name),
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(row)
            created.append(row)
            known_slugs.add(key)
        db.add(
            SiteSetting(
                key=city_marker_key,
                value="true",
                updated_at=datetime.utcnow(),
            )
        )
        db.flush()

    # The province column was added after cities became administrator-managed.
    # Reconcile the canonical map on every start because the original seed
    # marker already exists in production.
    for row in existing:
        if row.kind != "city":
            continue
        canonical_province = PAKISTAN_PROVINCE_BY_CITY.get(row.name)
        if canonical_province and row.province != canonical_province:
            row.province = canonical_province
            row.updated_at = datetime.utcnow()
            db.add(row)
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


def _canonicalize_job_cities_from_rows(
    values: list[str], rows: list[TaxonomyTerm]
) -> list[str]:
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
                "Select only predefined cities. Unknown: "
                + ", ".join(unknown[:10])
            ),
        )
    return result


def canonicalize_job_cities(db: Session, values: list[str]) -> list[str]:
    ensure_default_taxonomy(db)
    rows = (
        db.execute(select(TaxonomyTerm).where(TaxonomyTerm.kind == "city"))
        .scalars()
        .all()
    )
    return _canonicalize_job_cities_from_rows(values, rows)


def canonicalize_job_provinces(values: list[str]) -> list[str]:
    allowed = {value.casefold(): value for value in PAKISTAN_PROVINCES}
    result: list[str] = []
    seen: set[str] = set()
    unknown: list[str] = []
    for raw in values:
        clean = str(raw).strip()
        if not clean:
            continue
        canonical = allowed.get(clean.casefold())
        if not canonical:
            unknown.append(clean)
            continue
        key = canonical.casefold()
        if key not in seen:
            seen.add(key)
            result.append(canonical)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                "Select only predefined provinces/territories. Unknown: "
                + ", ".join(unknown[:10])
            ),
        )
    return result


def canonicalize_job_locations(
    db: Session,
    cities: list[str],
    provinces: list[str],
    *,
    city_rows: list[TaxonomyTerm] | None = None,
) -> tuple[list[str], list[str]]:
    """Return a truthful, internally consistent city/province assignment.

    Explicit cities own the province selection: a Karachi job cannot retain a
    stale Punjab value. Blank or legacy full-country selections collapse to the
    dedicated Pakistan-wide marker, which is displayed on all location pages.
    """
    if city_rows is None:
        ensure_default_taxonomy(db)
        city_rows = (
            db.execute(select(TaxonomyTerm).where(TaxonomyTerm.kind == "city"))
            .scalars()
            .all()
        )
    canonical_cities = _canonicalize_job_cities_from_rows(cities, city_rows)
    canonical_provinces = canonicalize_job_provinces(provinces)
    selected_city_keys = {value.casefold() for value in canonical_cities}
    selected_province_keys = {value.casefold() for value in canonical_provinces}
    all_city_keys = {value.casefold() for value in PAKISTAN_CITIES}
    all_province_keys = {value.casefold() for value in PAKISTAN_PROVINCES}

    if (
        PAKISTAN_ALL_CITIES.casefold() in selected_city_keys
        or (all_city_keys and all_city_keys.issubset(selected_city_keys))
        or (
            len(selected_city_keys) >= 20
            and len(selected_city_keys & all_city_keys) / len(all_city_keys) >= 0.9
        )
        or (all_province_keys and all_province_keys.issubset(selected_province_keys))
    ):
        return [PAKISTAN_ALL_CITIES], []

    if canonical_cities:
        province_by_city = {
            row.name.casefold(): row.province
            for row in city_rows
            if row.province in PAKISTAN_PROVINCES
        }
        derived_provinces: list[str] = []
        seen: set[str] = set()
        for city in canonical_cities:
            province = (
                province_by_city.get(city.casefold())
                or PAKISTAN_PROVINCE_BY_CITY.get(city)
            )
            if province and province.casefold() not in seen:
                seen.add(province.casefold())
                derived_provinces.append(province)
        # A legacy custom city may predate province metadata. Preserve one
        # administrator-selected valid province rather than inventing a value.
        if not derived_provinces and len(canonical_provinces) == 1:
            derived_provinces = canonical_provinces
        return canonical_cities, derived_provinces

    if canonical_provinces:
        return [], canonical_provinces

    return [PAKISTAN_ALL_CITIES], []
