from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import PAKISTAN_PROVINCES
from app.models import BlogPost, Job, Page, SEOMeta, SiteSetting, TaxonomyTerm
from app.services.directory_pages import ensure_directory_pages
from app.services.seo import upsert_job_seo, upsert_page_seo
from app.services.taxonomy import canonicalize_job_locations
from app.utils import as_list

ORGANIZATION_ALIAS_SETTING = "organization_directory_aliases"
_EMPTY_TEXT = {"", "none", "null"}
_LEGAL_SUFFIXES = {
    "co",
    "company",
    "limited",
    "ltd",
    "private",
    "pvt",
}
_ACRONYM_STOPWORDS = {"and", "of", "the", "for"}


def clean_optional_text(value: Any) -> str | None:
    """Normalize an optional plain-text field to useful content or NULL."""
    if value is None:
        return None
    clean = str(value).strip()
    return None if clean.casefold() in _EMPTY_TEXT else clean


def clean_optional_list(value: Any) -> list[str] | None:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in as_list(value):
        text = clean_optional_text(item)
        if not text or text.casefold() in seen:
            continue
        seen.add(text.casefold())
        cleaned.append(text)
    return cleaned or None


def _ascii_words(value: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    folded = folded.casefold().replace("&", " and ")
    return re.findall(r"[a-z0-9]+", folded)


def _organization_key(value: str) -> str:
    words = _ascii_words(value)
    while words and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return "".join(words)


def _organization_acronyms(value: str) -> set[str]:
    words = [word for word in _ascii_words(value) if word not in _ACRONYM_STOPWORDS]
    acronyms = {"".join(word[0] for word in words if word)}
    acronyms.update(
        "".join(_ascii_words(parenthetical))
        for parenthetical in re.findall(r"\(([^)]+)\)", value)
    )
    return {acronym for acronym in acronyms if 2 < len(acronym) <= 10}


def organizations_equivalent(left: str | None, right: str | None) -> bool:
    """Conservatively identify the same organization under harmless variants.

    Exact punctuation/legal-suffix variants and a genuine acronym/full-name pair
    merge. Fuzzy matching is deliberately restricted to very long, near-identical
    names so unrelated short agencies (for example ECP and SECP) stay separate.
    """
    left_clean = clean_optional_text(left)
    right_clean = clean_optional_text(right)
    if not left_clean or not right_clean:
        return False
    left_key = _organization_key(left_clean)
    right_key = _organization_key(right_clean)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    shorter, longer = sorted((left_key, right_key), key=len)
    if 2 < len(shorter) <= 10:
        longer_source = right_clean if longer == right_key else left_clean
        if shorter in _organization_acronyms(longer_source):
            return True
    return (
        min(len(left_key), len(right_key)) >= 12
        and SequenceMatcher(None, left_key, right_key).ratio() >= 0.96
    )


def _organization_groups(values: Iterable[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    for value in values:
        for group in groups:
            if any(organizations_equivalent(value, existing) for existing in group):
                group.append(value)
                break
        else:
            groups.append([value])
    # A newly-added variant can bridge two existing groups, so close transitive
    # overlaps before choosing canonical display values.
    changed = True
    while changed:
        changed = False
        for index, group in enumerate(groups):
            for other_index in range(index + 1, len(groups)):
                if any(
                    organizations_equivalent(a, b)
                    for a in group
                    for b in groups[other_index]
                ):
                    group.extend(groups.pop(other_index))
                    changed = True
                    break
            if changed:
                break
    return groups


def _canonical_organization(group: list[str], counts: Counter[str]) -> str:
    return sorted(
        group,
        key=lambda value: (
            -counts[value.casefold()],
            bool(re.fullmatch(r"[A-Z0-9& .-]{2,12}", value)),
            -len(value),
            value.casefold(),
        ),
    )[0]


def canonicalize_job_organization(db: Session, value: Any) -> str | None:
    clean = clean_optional_text(value)
    if not clean:
        return None
    candidates = {
        candidate
        for candidate in db.execute(select(Job.source).where(Job.source.is_not(None))).scalars()
        if clean_optional_text(candidate)
    }
    candidates.update(
        candidate
        for candidate in db.execute(
            select(Page.taxonomy_value).where(
                Page.page_type == "organization",
                Page.taxonomy_value.is_not(None),
            )
        ).scalars()
        if clean_optional_text(candidate)
    )
    matches = [candidate for candidate in candidates if organizations_equivalent(clean, candidate)]
    if not matches:
        return clean
    counts = Counter(
        (source or "").casefold()
        for source in db.execute(select(Job.source)).scalars()
        if clean_optional_text(source)
    )
    return _canonical_organization([clean, *matches], counts)


def organization_aliases(db: Session) -> dict[str, str]:
    setting = db.get(SiteSetting, ORGANIZATION_ALIAS_SETTING)
    if not setting or not setting.value:
        return {}
    try:
        value = json.loads(setting.value)
        return {
            str(alias): str(canonical)
            for alias, canonical in value.items()
            if alias and canonical
        } if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _save_organization_aliases(db: Session, aliases: dict[str, str]) -> None:
    setting = db.get(SiteSetting, ORGANIZATION_ALIAS_SETTING)
    if not setting:
        setting = SiteSetting(key=ORGANIZATION_ALIAS_SETTING)
        db.add(setting)
    setting.value = json.dumps(dict(sorted(aliases.items())))
    setting.updated_at = datetime.utcnow()


def repair_job_data_quality(db: Session) -> dict[str, int]:
    """Idempotently repair legacy job taxonomy and empty optional values."""
    jobs = db.execute(select(Job)).scalars().all()
    organization_pages = db.execute(
        select(Page).where(Page.page_type == "organization")
    ).scalars().all()
    city_rows = db.execute(
        select(TaxonomyTerm).where(TaxonomyTerm.kind == "city")
    ).scalars().all()
    values = {
        clean
        for clean in (
            clean_optional_text(value)
            for value in [
                *(job.source for job in jobs),
                *(page.taxonomy_value for page in organization_pages),
            ]
        )
        if clean
    }
    counts = Counter(
        clean.casefold()
        for clean in (clean_optional_text(job.source) for job in jobs)
        if clean
    )
    organization_groups = _organization_groups(sorted(values, key=str.casefold))
    canonical_by_value: dict[str, str] = {}
    for group in organization_groups:
        canonical = _canonical_organization(group, counts)
        for value in group:
            canonical_by_value[value.casefold()] = canonical

    repaired_jobs = 0
    for job in jobs:
        before = (
            job.source,
            job.salary_range,
            job.newspaper,
            job.reference_url,
            job.application_url,
            job.experience_required,
            job.education_required,
            job.skills,
            job.job_type,
            job.cities,
            job.provinces,
            job.tags,
            job.keywords,
        )
        source = clean_optional_text(job.source)
        job.source = canonical_by_value.get(source.casefold(), source) if source else None
        for field in (
            "salary_range",
            "newspaper",
            "reference_url",
            "application_url",
            "experience_required",
            "education_required",
            "job_type",
            "keywords",
        ):
            setattr(job, field, clean_optional_text(getattr(job, field)))
        job.skills = clean_optional_list(job.skills)
        job.tags = clean_optional_list(job.tags)
        try:
            cities, provinces = canonicalize_job_locations(
                db,
                as_list(job.cities),
                as_list(job.provinces),
                city_rows=city_rows,
            )
        except HTTPException:
            valid_provinces = [
                value
                for value in as_list(job.provinces)
                if value in PAKISTAN_PROVINCES
            ]
            cities, provinces = canonicalize_job_locations(
                db,
                as_list(job.cities),
                valid_provinces,
                city_rows=city_rows,
            )
        job.cities = cities or None
        job.provinces = provinces or None
        after = (
            job.source,
            job.salary_range,
            job.newspaper,
            job.reference_url,
            job.application_url,
            job.experience_required,
            job.education_required,
            job.skills,
            job.job_type,
            job.cities,
            job.provinces,
            job.tags,
            job.keywords,
        )
        if before != after:
            repaired_jobs += 1
            job.updated_at = datetime.utcnow()
            upsert_job_seo(db, job)

    aliases = organization_aliases(db)
    merged_pages = 0
    for group in organization_groups:
        canonical = _canonical_organization(group, counts)
        matching = [
            page
            for page in organization_pages
            if page.taxonomy_value
            and any(
                page.taxonomy_value.casefold() == value.casefold()
                for value in group
            )
        ]
        if len(matching) < 2:
            if matching and matching[0].taxonomy_value != canonical:
                matching[0].taxonomy_value = canonical
                upsert_page_seo(db, matching[0])
            continue
        canonical_page = next(
            (
                page
                for page in matching
                if (page.taxonomy_value or "").casefold() == canonical.casefold()
            ),
            sorted(
                matching,
                key=lambda page: (
                    not page.is_published,
                    page.created_at or datetime.min,
                ),
            )[0],
        )
        canonical_page.taxonomy_value = canonical
        canonical_page.is_published = True
        canonical_page.updated_at = datetime.utcnow()
        upsert_page_seo(db, canonical_page)
        for page in matching:
            if page.id == canonical_page.id:
                continue
            if page.slug != canonical_page.slug:
                aliases[page.slug.casefold()] = canonical_page.slug
            if page.is_published:
                merged_pages += 1
            page.is_published = False
            page.updated_at = datetime.utcnow()

    # Normalize optional content metadata too. Required content fields stay as
    # valid strings; optional unknown facts become SQL NULL.
    normalized_optional = 0
    for post in db.execute(select(BlogPost)).scalars():
        for field in ("excerpt", "author", "category"):
            old = getattr(post, field)
            new = clean_optional_text(old)
            if old != new:
                setattr(post, field, new)
                normalized_optional += 1
        cleaned_tags = clean_optional_list(post.tags)
        if post.tags != cleaned_tags:
            post.tags = cleaned_tags
            normalized_optional += 1
    for seo in db.execute(select(SEOMeta)).scalars():
        for field in (
            "slug",
            "meta_title",
            "meta_description",
            "meta_keywords",
            "focus_keyword",
            "og_title",
            "og_description",
            "og_image",
            "canonical_url",
            "robots",
            "h1",
        ):
            old = getattr(seo, field)
            new = clean_optional_text(old)
            if old != new:
                setattr(seo, field, new)
                normalized_optional += 1

    _save_organization_aliases(db, aliases)
    ensure_directory_pages(
        db,
        {
            "city": [value for job in jobs for value in as_list(job.cities)],
            "province": [value for job in jobs for value in as_list(job.provinces)],
            "category": [value for job in jobs for value in as_list(job.tags)],
            "organization": [job.source for job in jobs],
            "newspaper": [job.newspaper for job in jobs],
        },
    )
    db.flush()
    return {
        "jobs": repaired_jobs,
        "organization_pages": merged_pages,
        "optional_fields": normalized_optional,
    }
