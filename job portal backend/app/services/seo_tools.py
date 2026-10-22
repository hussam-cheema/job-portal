from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import canonical_site_url, env, site_url
from app.logging_config import get_logger
from app.models import (
    BlogPost,
    Job,
    Page,
    SEOBacklink,
    SEOKeywordRank,
    SEOMeta,
    SiteSetting,
    TaxonomyTerm,
    ToolCategory,
    ToolPage,
)
from app.page_types import DIRECT_PAGE_SLUGS, public_page_path
from app.constants import (
    PAKISTAN_ALL_CITIES,
    PAKISTAN_CITIES,
    PAKISTAN_CITIES_BY_PROVINCE,
    PAKISTAN_PROVINCE_BY_CITY,
    PAKISTAN_PROVINCES,
)
from app.utils import as_list, slugify
from app.services.directory_pages import (
    canonical_directory_pages,
    directory_taxonomy_key,
    normalize_directory_page_title,
)
from app.services.job_indexing import job_index_status

logger = get_logger("jobportal.seo_tools")

GSC_SEARCH_ANALYTICS_PAGE_SIZE = 25_000


def _indexable_directory_state(db: Session):
    """Return active directory keys and sitemap dates from search-ready jobs."""
    all_indexable_jobs = [
        job
        for job in db.execute(select(Job)).scalars().all()
        if job_index_status(job).indexable
    ]
    jobs = [
        job for job in all_indexable_jobs if not job_index_status(job).archived
    ]
    dynamic_cities_by_province: dict[str, list[str]] = {}
    for city_name, province_name in db.execute(
        select(TaxonomyTerm.name, TaxonomyTerm.province).where(
            TaxonomyTerm.kind == "city",
            TaxonomyTerm.is_active.is_(True),
            TaxonomyTerm.province.is_not(None),
        )
    ).all():
        dynamic_cities_by_province.setdefault(province_name, []).append(city_name)

    active_keys: dict[str, set[str]] = {
        "category": set(),
        "city": set(),
        "province": set(),
        "organization": set(),
        "newspaper": set(),
    }
    active_dates: dict[str, dict[str, datetime]] = {
        page_type: {} for page_type in active_keys
    }
    job_tags: dict[str, datetime | None] = {}
    qualifications: dict[str, datetime | None] = {}

    def track(page_type: str, value: Any) -> None:
        key = directory_taxonomy_key(page_type, value)
        if not key:
            return
        active_keys[page_type].add(key)

    for job in jobs:
        modified = job.updated_at or job.published_date or datetime.min
        job_values = {
            value.strip() for value in as_list(job.tags) if value and value.strip()
        }
        for value in job_values:
            track("category", value)
            previous = job_tags.get(value)
            if previous is None or modified > previous:
                job_tags[value] = modified
        if job.source and job.source.strip():
            track("organization", job.source)
        if job.newspaper and job.newspaper.strip():
            track("newspaper", job.newspaper)
        expanded_cities, expanded_provinces = _expanded_job_locations(
            job, dynamic_cities_by_province
        )
        for value in expanded_cities:
            track("city", value)
        for value in expanded_provinces:
            track("province", value)
        if job.education_required and job.education_required.strip():
            previous = qualifications.get(job.education_required.strip())
            if previous is None or modified > previous:
                qualifications[job.education_required.strip()] = modified

        for page_type, values in (
            ("category", job_values),
            ("organization", [job.source] if job.source else []),
            ("newspaper", [job.newspaper] if job.newspaper else []),
            ("city", expanded_cities),
            ("province", expanded_provinces),
        ):
            for value in values:
                key = directory_taxonomy_key(page_type, value)
                if key:
                    previous = active_dates[page_type].get(key)
                    if previous is None or modified > previous:
                        active_dates[page_type][key] = modified

    return (
        all_indexable_jobs,
        active_keys,
        active_dates,
        job_tags,
        qualifications,
    )


def build_indexable_directory_keys(db: Session) -> dict[str, set[str]]:
    """Return directory keys backed by at least one search-ready active job."""
    return _indexable_directory_state(db)[1]


def gsc_credentials_configured() -> bool:
    """Return whether either file-based or environment-based GSC credentials exist."""
    return bool(
        env("GSC_SERVICE_ACCOUNT_JSON")
        or env("GOOGLE_SERVICE_ACCOUNT_JSON")
        or env("GOOGLE_APPLICATION_CREDENTIALS")
    )


def _build_gsc_credentials(scopes: list[str]):
    """Build Google credentials from a serverless secret or mounted JSON file."""
    from google.oauth2 import service_account

    raw_credentials = env("GSC_SERVICE_ACCOUNT_JSON") or env(
        "GOOGLE_SERVICE_ACCOUNT_JSON"
    )
    if raw_credentials:
        credential_info = json.loads(raw_credentials)
        if not isinstance(credential_info, dict):
            raise ValueError("Google service-account JSON must be an object")
        return service_account.Credentials.from_service_account_info(
            credential_info,
            scopes=scopes,
        )

    credentials_path = env("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_path and os.path.exists(credentials_path):
        return service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=scopes,
        )
    return None


def get_setting(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.get(SiteSetting, key)
    if row and row.value is not None:
        return row.value
    return default


def set_setting(db: Session, key: str, value: str | None) -> None:
    row = db.get(SiteSetting, key)
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        db.add(SiteSetting(key=key, value=value, updated_at=datetime.utcnow()))
    db.commit()


def get_social_settings(db: Session) -> dict[str, str]:
    return {
        "facebook_url": get_setting(db, "social_facebook", "") or "",
        "youtube_url": get_setting(db, "social_youtube", "") or "",
        "x_url": get_setting(db, "social_x", "") or "",
        "linkedin_url": get_setting(db, "social_linkedin", "") or "",
    }


def set_social_settings(db: Session, data: dict[str, str]) -> dict[str, str]:
    mapping = {
        "facebook_url": "social_facebook",
        "youtube_url": "social_youtube",
        "x_url": "social_x",
        "linkedin_url": "social_linkedin",
    }
    for k, sk in mapping.items():
        if k in data:
            set_setting(db, sk, (data.get(k) or "").strip() or None)
    return get_social_settings(db)


def build_sitemap_urls(db: Session) -> list[dict[str, Any]]:
    from app.models import MarketReport
    base = canonical_site_url()
    urls: list[dict[str, Any]] = [
        {"loc": f"{base}/", "changefreq": "daily", "priority": 1.0},
        {"loc": f"{base}/about", "changefreq": "monthly", "priority": 0.6},
        {"loc": f"{base}/contact", "changefreq": "monthly", "priority": 0.5},
        {"loc": f"{base}/privacy", "changefreq": "yearly", "priority": 0.3},
        {"loc": f"{base}/disclaimer", "changefreq": "yearly", "priority": 0.3},
        {"loc": f"{base}/editorial-policy", "changefreq": "monthly", "priority": 0.5},
        {"loc": f"{base}/archive", "changefreq": "weekly", "priority": 0.5},
        {"loc": f"{base}/blog", "changefreq": "daily", "priority": 0.8},
        {"loc": f"{base}/dashboard", "changefreq": "monthly", "priority": 0.9},
        {"loc": f"{base}/browse", "changefreq": "daily", "priority": 0.8},
        {"loc": f"{base}/tools/resume-builder", "changefreq": "monthly", "priority": 0.6},
        {"loc": f"{base}/tools/cover-letter", "changefreq": "monthly", "priority": 0.6},
        {"loc": f"{base}/tools", "changefreq": "weekly", "priority": 0.8},
        {"loc": f"{base}/jobs-by-cities", "changefreq": "weekly", "priority": 0.7},
        {"loc": f"{base}/jobs-by-provinces", "changefreq": "weekly", "priority": 0.7},
        {"loc": f"{base}/jobs-by-categories", "changefreq": "weekly", "priority": 0.7},
        {"loc": f"{base}/jobs-by-organizations", "changefreq": "weekly", "priority": 0.7},
        {"loc": f"{base}/jobs-by-newspapers", "changefreq": "weekly", "priority": 0.7},
    ]
    try:
        (
            jobs,
            active_keys,
            active_dates,
            job_tags,
            qualifications,
        ) = _indexable_directory_state(db)
        for job in jobs:
            urls.append(
                {
                    "loc": f"{base}/jobs/{job.slug or job.id}",
                    "lastmod": (
                        job.updated_at or job.published_date or datetime.utcnow()
                    )
                    .date()
                    .isoformat(),
                    "changefreq": "weekly",
                    "priority": 0.8,
                }
            )
        for value in sorted(job_tags):
            if slugify(value):
                urls.append(
                    {
                        "loc": f"{base}/tags/{slugify(value)}",
                        "lastmod": job_tags[value].date().isoformat(),
                        "changefreq": "weekly",
                        "priority": 0.5,
                    }
                )
        for value in sorted(qualifications):
            if slugify(value):
                urls.append(
                    {
                        "loc": f"{base}/qualifications/{slugify(value)}",
                        "lastmod": qualifications[value].date().isoformat(),
                        "changefreq": "weekly",
                        "priority": 0.5,
                    }
                )
        pages = db.execute(
            select(
                Page.slug,
                Page.title,
                Page.page_type,
                Page.taxonomy_value,
                Page.updated_at,
            ).where(Page.is_published.is_(True))
        ).all()
        directory_pages = canonical_directory_pages(
            [page for page in pages if page.page_type != "standard"],
            active_keys=active_keys,
        )
        for page in [page for page in pages if page.page_type == "standard"] + directory_pages:
            path = public_page_path(page.page_type, page.slug)
            if page.page_type == "standard" and page.slug in DIRECT_PAGE_SLUGS:
                continue  # already added static
            directory_key = directory_taxonomy_key(
                page.page_type, page.taxonomy_value
            )
            modified = active_dates.get(page.page_type, {}).get(directory_key)
            if page.page_type in active_keys and modified is None:
                continue
            urls.append(
                {
                    "loc": f"{base}{path}",
                    "lastmod": (modified or page.updated_at or datetime.utcnow())
                    .date()
                    .isoformat(),
                    "changefreq": "monthly",
                    "priority": 0.5,
                }
            )
        for category in db.execute(
            select(ToolCategory.slug, ToolCategory.updated_at).where(
                ToolCategory.is_published.is_(True)
            )
        ).all():
            urls.append(
                {
                    "loc": f"{base}/tools/categories/{category.slug}",
                    "lastmod": (category.updated_at or datetime.utcnow()).date().isoformat(),
                    "changefreq": "monthly",
                    "priority": 0.6,
                }
            )
        for tool in db.execute(
            select(ToolPage.slug, ToolPage.updated_at).where(
                ToolPage.is_published.is_(True)
            )
        ).all():
            urls.append(
                {
                    "loc": f"{base}/tools/{tool.slug}",
                    "lastmod": (tool.updated_at or datetime.utcnow()).date().isoformat(),
                    "changefreq": "monthly",
                    "priority": 0.7,
                }
            )
        now = datetime.utcnow()
        posts = db.execute(
            select(
                BlogPost.slug,
                BlogPost.updated_at,
                BlogPost.published_at,
                BlogPost.category,
                BlogPost.tags,
            ).where(
                BlogPost.is_published.is_(True),
                (BlogPost.published_at.is_(None) | (BlogPost.published_at <= now)),
            )
        ).all()
        blog_categories: set[str] = set()
        blog_tags: set[str] = set()
        for post in posts:
            urls.append(
                {
                    "loc": f"{base}/blog/{post.slug}",
                    "lastmod": (post.updated_at or post.published_at or now)
                    .date()
                    .isoformat(),
                    "changefreq": "weekly",
                    "priority": 0.7,
                }
            )
            if post.category and post.category.strip():
                blog_categories.add(post.category.strip())
            blog_tags.update(
                value.strip() for value in as_list(post.tags) if value and value.strip()
            )
        for value in sorted(blog_categories):
            if slugify(value):
                urls.append(
                    {
                        "loc": f"{base}/blog/categories/{slugify(value)}",
                        "changefreq": "weekly",
                        "priority": 0.5,
                    }
                )
        for value in sorted(blog_tags):
            if slugify(value):
                urls.append(
                    {
                        "loc": f"{base}/blog/tags/{slugify(value)}",
                        "changefreq": "weekly",
                        "priority": 0.4,
                    }
                )
    except Exception:
        logger.exception("build_sitemap_urls failed")
    for report_month, published_at in db.execute(select(MarketReport.month, MarketReport.published_at)).all():
        urls.append({"loc": f"{base}/dashboard/{report_month}", "lastmod": published_at.isoformat() + "Z", "changefreq": "yearly", "priority": 0.8})
    return list({item["loc"]: item for item in urls}.values())


def _directory_values(
    values: list[str], seeds: list[str] | None = None
) -> list[dict[str, Any]]:
    """Return stable, deduplicated public directory values with link metadata."""
    display_by_key: dict[str, str] = {}
    counts: dict[str, int] = {}
    for raw_value in seeds or []:
        value = (raw_value or "").strip()
        value_slug = slugify(value)
        if not value or not value_slug:
            continue
        key = value.casefold()
        display_by_key.setdefault(key, value)
        counts.setdefault(key, 0)
    for raw_value in values:
        value = (raw_value or "").strip()
        value_slug = slugify(value)
        if not value or not value_slug:
            continue
        key = value.casefold()
        display_by_key.setdefault(key, value)
        counts[key] = counts.get(key, 0) + 1
    return [
        {
            "name": display_by_key[key],
            "slug": slugify(display_by_key[key]),
            "count": counts[key],
        }
        for key in sorted(
            display_by_key, key=lambda item: display_by_key[item].casefold()
        )
    ]


def _directory_page_values(
    pages: list[Any],
    page_type: str,
    raw_values: list[str],
    *,
    include_empty: bool = True,
) -> list[dict[str, Any]]:
    """Expose only published CMS pages while retaining live job counts."""
    count_by_value: dict[str, int] = {}
    for value in raw_values:
        key = directory_taxonomy_key(page_type, value)
        if key:
            count_by_value[key] = count_by_value.get(key, 0) + 1
    canonical_pages = canonical_directory_pages(
        [page for page in pages if page.page_type == page_type]
    )
    return [
        {
            "name": normalize_directory_page_title(page.title),
            "slug": page.slug,
            "count": count_by_value.get(
                directory_taxonomy_key(page_type, page.taxonomy_value), 0
            ),
            "page_id": page.id,
            "taxonomy_value": page.taxonomy_value,
        }
        for page in sorted(
            canonical_pages,
            key=lambda item: normalize_directory_page_title(item.title).casefold(),
        )
        if page.taxonomy_value
        and (
            include_empty
            or count_by_value.get(
                directory_taxonomy_key(page_type, page.taxonomy_value), 0
            )
            > 0
        )
    ]


def _expanded_job_locations(
    job: Any,
    cities_by_province: dict[str, list[str]] | None = None,
    all_cities: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Count jobs on every city/province directory where they are displayed."""
    selected_cities = set(as_list(job.cities))
    selected_provinces = set(as_list(job.provinces))
    lowered = {value.casefold() for value in selected_cities | selected_provinces}
    nationwide = (
        "pakistan" in lowered
        or set(PAKISTAN_CITIES).issubset(selected_cities)
        or (
            len(selected_cities) >= 20
            and len(selected_cities & set(PAKISTAN_CITIES)) / len(PAKISTAN_CITIES) >= 0.9
        )
        or set(PAKISTAN_PROVINCES).issubset(selected_provinces)
    )
    if nationwide:
        return sorted(
            {PAKISTAN_ALL_CITIES, *(all_cities or PAKISTAN_CITIES)},
            key=str.casefold,
        ), list(PAKISTAN_PROVINCES)

    expanded_cities = set(selected_cities)
    expanded_provinces = set(selected_provinces)
    if not selected_cities:
        for province in selected_provinces:
            expanded_cities.update(PAKISTAN_CITIES_BY_PROVINCE.get(province, []))
            expanded_cities.update((cities_by_province or {}).get(province, []))
    for city in selected_cities:
        province = PAKISTAN_PROVINCE_BY_CITY.get(city)
        if not province:
            province = next(
                (
                    province_name
                    for province_name, city_names in (cities_by_province or {}).items()
                    if city in city_names
                ),
                None,
            )
        if province:
            expanded_provinces.add(province)
    return sorted(expanded_cities, key=str.casefold), sorted(
        expanded_provinces, key=str.casefold
    )


def build_site_directory(db: Session) -> dict[str, Any]:
    """Build the complete public link inventory used by Browse All and crawl tests."""
    now = datetime.utcnow()
    jobs = db.execute(
        select(
            Job.id,
            Job.slug,
            Job.title,
            Job.published_date,
            Job.deadline_date,
            Job.salary_range,
            Job.source,
            Job.newspaper,
            Job.education_required,
            Job.experience_required,
            Job.job_type,
            Job.cities,
            Job.provinces,
            Job.tags,
        ).order_by(Job.published_date.desc(), Job.created_at.desc())
    ).all()
    posts = db.execute(
        select(
            BlogPost.id,
            BlogPost.slug,
            BlogPost.title,
            BlogPost.published_at,
            BlogPost.category,
            BlogPost.tags,
        )
        .where(
            BlogPost.is_published.is_(True),
            (BlogPost.published_at.is_(None) | (BlogPost.published_at <= now)),
        )
        .order_by(BlogPost.published_at.desc(), BlogPost.created_at.desc())
    ).all()
    pages = db.execute(
        select(
            Page.id,
            Page.slug,
            Page.title,
            Page.page_type,
            Page.taxonomy_value,
            Page.updated_at,
        )
        .where(Page.is_published.is_(True))
        .order_by(Page.title.asc())
    ).all()
    job_tags = [value for job in jobs for value in set(as_list(job.tags))]
    city_terms = db.execute(
        select(TaxonomyTerm.name, TaxonomyTerm.province).where(
            TaxonomyTerm.kind == "city",
            TaxonomyTerm.is_active.is_(True),
            TaxonomyTerm.province.is_not(None),
        )
    ).all()
    dynamic_cities_by_province: dict[str, list[str]] = {}
    for city_name, province_name in city_terms:
        dynamic_cities_by_province.setdefault(province_name, []).append(city_name)
    all_cities = {
        *PAKISTAN_CITIES,
        *(city_name for city_name, _ in city_terms),
        *(
            page.taxonomy_value
            for page in pages
            if page.page_type == "city" and page.taxonomy_value
        ),
    }
    expanded_locations = [
        _expanded_job_locations(job, dynamic_cities_by_province, all_cities)
        for job in jobs
    ]
    cities = [value for city_values, _ in expanded_locations for value in city_values]
    provinces = [
        value for _, province_values in expanded_locations for value in province_values
    ]
    organizations = [job.source or "" for job in jobs]
    newspapers = [job.newspaper or "" for job in jobs]
    qualifications = [job.education_required or "" for job in jobs]
    blog_categories = [post.category or "" for post in posts]
    blog_tags = [value for post in posts for value in as_list(post.tags)]

    return {
        "generated_at": now.isoformat(),
        "jobs": [
            {
                "id": job.id,
                "slug": job.slug or job.id,
                "title": job.title,
                "published_date": job.published_date.isoformat()
                if job.published_date
                else None,
                "deadline_date": job.deadline_date.isoformat()
                if job.deadline_date
                else None,
                "applications_closed": bool(
                    job.deadline_date and job.deadline_date.date() < now.date()
                ),
                "organization": (job.source or "").strip() or None,
                "newspaper": (job.newspaper or "").strip() or None,
                "salary_range": (job.salary_range or "").strip() or None,
                "education_required": (job.education_required or "").strip()
                or None,
                "experience_required": (job.experience_required or "").strip()
                or None,
                "job_type": job.job_type,
                "category": next(iter(as_list(job.tags)), None),
                "cities": as_list(job.cities),
                "provinces": as_list(job.provinces),
                "tags": as_list(job.tags),
            }
            for job in jobs
        ],
        "blogs": [
            {
                "id": post.id,
                "slug": post.slug,
                "title": post.title,
                "published_at": post.published_at.isoformat()
                if post.published_at
                else None,
                "category": post.category,
                "tags": as_list(post.tags),
            }
            for post in posts
        ],
        "pages": [
            {
                "id": page.id,
                "slug": page.slug,
                "title": page.title,
                "page_type": page.page_type,
                "taxonomy_value": page.taxonomy_value,
                "path": public_page_path(page.page_type, page.slug),
            }
            for page in pages
        ],
        "taxonomies": {
            "job_categories": _directory_page_values(
                pages, "category", job_tags, include_empty=False
            ),
            "job_tags": _directory_values(job_tags),
            "cities": _directory_page_values(
                pages, "city", cities, include_empty=False
            ),
            "provinces": _directory_page_values(
                pages, "province", provinces, include_empty=False
            ),
            "organizations": _directory_page_values(
                pages, "organization", organizations, include_empty=False
            ),
            "newspapers": _directory_page_values(
                pages, "newspaper", newspapers, include_empty=False
            ),
            "qualifications": _directory_values(qualifications),
            "blog_categories": _directory_values(blog_categories),
            "blog_tags": _directory_values(blog_tags),
        },
    }


def robots_txt() -> str:
    base = canonical_site_url()
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /login\n"
        "Disallow: /api/\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )


def measure_pagespeed(url: str | None = None) -> dict[str, Any]:
    """
    Page speed out of 100 using Google PageSpeed Insights API (free) when
    PAGESPEED_API_KEY is set; otherwise a local on-page proxy score.
    """
    target = url or site_url()
    api_key = env("PAGESPEED_API_KEY") or env("GOOGLE_PAGESPEED_API_KEY")
    if api_key:
        try:
            endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
            params = {
                "url": target,
                "category": "performance",
                "strategy": "mobile",
                "key": api_key,
            }
            with httpx.Client(timeout=60.0) as client:
                r = client.get(endpoint, params=params)
                r.raise_for_status()
                data = r.json()
            lh = data.get("lighthouseResult") or {}
            cats = lh.get("categories") or {}
            perf = ((cats.get("performance") or {}).get("score") or 0) * 100
            audits = lh.get("audits") or {}
            return {
                "score": round(perf, 1),
                "source": "pagespeed_insights",
                "url": target,
                "fcp_ms": (audits.get("first-contentful-paint") or {}).get(
                    "numericValue"
                ),
                "lcp_ms": (audits.get("largest-contentful-paint") or {}).get(
                    "numericValue"
                ),
                "cls": (audits.get("cumulative-layout-shift") or {}).get(
                    "numericValue"
                ),
                "tbt_ms": (audits.get("total-blocking-time") or {}).get("numericValue"),
            }
        except Exception as exc:
            logger.exception("pagespeed api failed")
            return {
                "score": 0,
                "source": "pagespeed_error",
                "error": str(exc),
                "url": target,
            }

    # Local fallback: measure TTFB (try public URL, then in-network frontend/backend health)
    candidates = [target]
    if "localhost:3000" in target or "127.0.0.1:3000" in target:
        candidates.extend(
            [
                env("INTERNAL_FRONTEND_URL") or "http://frontend:3000",
                "http://127.0.0.1:8000/health",
            ]
        )
    else:
        candidates.append("http://127.0.0.1:8000/health")

    import time

    last_err = None
    for url in candidates:
        try:
            t0 = time.time()
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                r = client.get(url)
                elapsed = (time.time() - t0) * 1000
                ok = r.status_code < 400
            if elapsed < 200:
                score = 95
            elif elapsed < 500:
                score = 85
            elif elapsed < 1000:
                score = 70
            elif elapsed < 2000:
                score = 55
            else:
                score = 35
            if not ok:
                score = min(score, 40)
            return {
                "score": score,
                "source": "local_ttfb",
                "url": url,
                "ttfb_ms": round(elapsed, 1),
                "status_code": r.status_code,
                "note": "Set PAGESPEED_API_KEY for full Lighthouse score (0–100).",
            }
        except Exception as exc:
            last_err = exc
            continue
    logger.exception("local speed measure failed")
    return {"score": 0, "source": "local_error", "error": str(last_err), "url": target}


def authority_score(db: Session) -> dict[str, Any]:
    """Composite free authority score from on-site SEO signals + backlinks count."""
    try:
        jobs_count = db.execute(select(func.count()).select_from(Job)).scalar() or 0
        pages_count = db.execute(select(func.count()).select_from(Page)).scalar() or 0
        seo_scores = (
            db.execute(select(SEOMeta.seo_score).where(SEOMeta.seo_score.is_not(None)))
            .scalars()
            .all()
        )
        metas_count = (
            db.execute(select(func.count()).select_from(SEOMeta)).scalar() or 0
        )
        bl_count = len(_unique_backlink_rows(db))
        avg_seo = sum(seo_scores) / len(seo_scores) if seo_scores else 40
        coverage = (metas_count / max(jobs_count + pages_count, 1)) * 100
        bl_component = min(30, bl_count * 2)
        score = round(min(100, avg_seo * 0.5 + coverage * 0.3 + bl_component), 1)
        return {
            "score": score,
            "avg_onpage_seo": round(avg_seo, 1),
            "seo_coverage_pct": round(coverage, 1),
            "backlinks": bl_count,
            "jobs": jobs_count,
            "pages": pages_count,
            "method": "composite_onpage_backlinks",
        }
    except Exception:
        logger.exception("authority_score failed")
        return {"score": 0, "method": "error"}


def _fetch_gsc_search_analytics_rows(
    service: Any,
    *,
    site: str,
    start: Any,
    end: Any,
    page_size: int = GSC_SEARCH_ANALYTICS_PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Fetch every available query/URL row using Search Console offsets."""
    page_size = max(1, min(int(page_size), GSC_SEARCH_ANALYTICS_PAGE_SIZE))
    start_row = 0
    rows: list[dict[str, Any]] = []

    while True:
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["query", "page"],
            "rowLimit": page_size,
            "startRow": start_row,
        }
        response = (
            service.searchanalytics()
            .query(siteUrl=site, body=body)
            .execute()
        )
        batch = response.get("rows") or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start_row += page_size

    return rows


def _count_unique_gsc_queries(rows: list[dict[str, Any]]) -> int:
    return len(
        {
            _normalized_keyword(item.get("keyword")).casefold()
            for item in rows
            if _normalized_keyword(item.get("keyword"))
        }
    )


def sync_gsc_data(db: Session) -> dict[str, Any]:
    """
    Pull Search Console search analytics when GSC_SITE_URL and either a
    service-account JSON environment secret or credential file are configured.
    """
    site = env("GSC_SITE_URL") or get_setting(db, "gsc_site_url")
    if not site or not gsc_credentials_configured():
        return {
            "connected": False,
            "message": "Connect Google Search Console: set GSC_SITE_URL and GSC_SERVICE_ACCOUNT_JSON (or GOOGLE_APPLICATION_CREDENTIALS).",
            "keywords": [],
            "pages": [],
        }
    try:
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
        credentials = _build_gsc_credentials(scopes)
        if credentials is None:
            return {
                "connected": False,
                "message": "The configured Google credential file is unavailable.",
                "keywords": [],
                "pages": [],
            }
        service = build(
            "searchconsole", "v1", credentials=credentials, cache_discovery=False
        )
        # Use an exact 28-day window and avoid today's still-changing data.
        end = datetime.utcnow().date() - timedelta(days=1)
        start = end - timedelta(days=27)
        rows = _fetch_gsc_search_analytics_rows(
            service,
            site=site,
            start=start,
            end=end,
        )

        # The dashboard represents the latest 28-day snapshot. Replace the
        # previous snapshot atomically so repeated syncs cannot append the same
        # keyword/URL rows indefinitely.
        db.execute(delete(SEOKeywordRank))
        keywords_out = []
        job_ids_by_slug = dict(db.execute(select(Job.slug, Job.id)).all())
        page_ids_by_slug = dict(db.execute(select(Page.slug, Page.id)).all())
        seen_pairs: set[tuple[str, str]] = set()
        for row in rows:
            keys = row.get("keys") or []
            if len(keys) < 2:
                continue
            query, page = keys[0], keys[1]
            pair = (
                str(query).strip().casefold(),
                str(page).strip().rstrip("/").casefold(),
            )
            if not pair[0] or not pair[1] or pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            pos = float(row.get("position") or 0)
            clicks = int(row.get("clicks") or 0)
            imps = int(row.get("impressions") or 0)
            ctr = float(row.get("ctr") or 0)
            entity_type, entity_id = _match_entity_from_maps(
                page,
                job_ids_by_slug=job_ids_by_slug,
                page_ids_by_slug=page_ids_by_slug,
            )
            db.add(
                SEOKeywordRank(
                    id=str(uuid4()),
                    keyword=query[:300],
                    url=page,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    position=pos,
                    # Kept for database compatibility only. Average position
                    # cannot be translated into a fixed Google results page.
                    search_page=1,
                    clicks=clicks,
                    impressions=imps,
                    ctr=ctr,
                    recorded_at=datetime.utcnow(),
                )
            )
            keywords_out.append(
                {
                    "keyword": query,
                    "url": page,
                    "position": pos,
                    "average_position": pos,
                    "clicks": clicks,
                    "impressions": imps,
                    "ctr": ctr,
                    "entity_type": entity_type,
                }
            )
        db.commit()
        unique_query_count = _count_unique_gsc_queries(keywords_out)
        unique_keywords = list_keyword_ranks(db, limit=50)
        set_setting(db, "gsc_last_sync", datetime.utcnow().isoformat())
        set_setting(db, "gsc_period_start", start.isoformat())
        set_setting(db, "gsc_period_end", end.isoformat())
        return {
            "connected": True,
            "site": site,
            "rows": unique_query_count,
            "query_url_rows": len(keywords_out),
            "keywords": unique_keywords[:50],
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "message": (
                f"Synced {unique_query_count} unique search queries across "
                f"{len(keywords_out)} query/URL rows from Google Search Console "
                f"for {start.isoformat()} to {end.isoformat()}."
            ),
        }
    except Exception as exc:
        db.rollback()
        logger.exception("gsc sync failed")
        return {
            "connected": False,
            "message": f"GSC sync failed: {exc}",
            "keywords": [],
            "pages": [],
        }


def _match_entity(db: Session, page_url: str) -> tuple[str | None, str | None]:
    try:
        path = urlparse(page_url).path.strip("/")
        if path.startswith("jobs/"):
            slug = path.split("/", 1)[1]
            job = db.execute(select(Job).where(Job.slug == slug)).scalar_one_or_none()
            if job:
                return "job", job.id
        elif path:
            slug = path.split("/")[-1]
            page = db.execute(
                select(Page).where(Page.slug == slug)
            ).scalar_one_or_none()
            if page:
                return "page", page.id
    except Exception:
        pass
    return None, None


def _match_entity_from_maps(
    page_url: str,
    *,
    job_ids_by_slug: dict[str, str],
    page_ids_by_slug: dict[str, str],
) -> tuple[str | None, str | None]:
    """Resolve a GSC URL without issuing a query for every search result row."""
    path = urlparse(page_url).path.strip("/")
    if path.startswith("jobs/"):
        job_id = job_ids_by_slug.get(path.split("/", 1)[1])
        return ("job", job_id) if job_id else (None, None)
    if path:
        page_id = page_ids_by_slug.get(path.split("/")[-1])
        return ("page", page_id) if page_id else (None, None)
    return None, None


def _normalized_keyword(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _keyword_url_rows(db: Session, limit: int = 1000) -> list[dict[str, Any]]:
    """Return the latest row for each normalized Search Console query/URL pair."""
    rows = (
        db.execute(
            select(SEOKeywordRank)
            .order_by(SEOKeywordRank.recorded_at.desc())
            .limit(max(limit, 200))
        )
        .scalars()
        .all()
    )
    unique_rows: list[SEOKeywordRank] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (
            _normalized_keyword(row.keyword).casefold(),
            row.url.strip().rstrip("/").casefold(),
        )
        if not key[0] or not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return [
        {
            "id": r.id,
            "keyword": _normalized_keyword(r.keyword),
            "url": r.url,
            "position": r.position,
            "average_position": r.position,
            "clicks": r.clicks,
            "impressions": r.impressions,
            "ctr": r.ctr,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
        }
        for r in unique_rows
    ]


def list_keyword_ranks(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    """Aggregate every URL-level GSC row into one unique normalized query."""
    rows = _keyword_url_rows(db, limit=max(limit * 20, 1000))
    by_keyword: dict[str, dict[str, Any]] = {}
    for row in rows:
        keyword = _normalized_keyword(row.get("keyword"))
        key = keyword.casefold()
        if not key:
            continue
        impressions = int(row.get("impressions") or 0)
        clicks = int(row.get("clicks") or 0)
        position = float(row.get("position") or 0)
        weight = impressions if impressions > 0 else 1
        candidate_score = (impressions, clicks, -position)
        aggregate = by_keyword.get(key)
        if aggregate is None:
            aggregate = {
                **row,
                "keyword": keyword,
                "impressions": 0,
                "clicks": 0,
                "ctr": 0.0,
                "position": 0.0,
                "average_position": 0.0,
                "url_count": 0,
                "_urls": set(),
                "_position_total": 0.0,
                "_position_weight": 0,
                "_top_url_score": candidate_score,
            }
            by_keyword[key] = aggregate
        elif candidate_score > aggregate["_top_url_score"]:
            aggregate["id"] = row["id"]
            aggregate["url"] = row["url"]
            aggregate["entity_type"] = row.get("entity_type")
            aggregate["entity_id"] = row.get("entity_id")
            aggregate["_top_url_score"] = candidate_score
        aggregate["impressions"] += impressions
        aggregate["clicks"] += clicks
        aggregate["_position_total"] += position * weight
        aggregate["_position_weight"] += weight
        aggregate["_urls"].add(row["url"].strip().rstrip("/").casefold())
        recorded_at = row.get("recorded_at")
        if recorded_at and (
            not aggregate.get("recorded_at") or recorded_at > aggregate["recorded_at"]
        ):
            aggregate["recorded_at"] = recorded_at

    aggregated: list[dict[str, Any]] = []
    for row in by_keyword.values():
        row["average_position"] = round(
            row.pop("_position_total") / max(row.pop("_position_weight"), 1),
            2,
        )
        row["position"] = row["average_position"]
        row["ctr"] = (
            round(row["clicks"] / row["impressions"], 6)
            if row["impressions"] > 0
            else 0.0
        )
        row["url_count"] = len(row.pop("_urls"))
        row.pop("_top_url_score", None)
        aggregated.append(row)
    aggregated.sort(
        key=lambda row: (
            -int(row["impressions"]),
            -int(row["clicks"]),
            float(row["average_position"]),
            str(row["keyword"]).casefold(),
        )
    )
    return aggregated[: max(1, limit)]


def _canonical_backlink_url(value: str | None) -> str:
    """Normalize inconsequential URL differences for backlink identity checks."""
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    scheme = parsed.scheme.casefold()
    hostname = (parsed.hostname or "").casefold()
    port = parsed.port
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        hostname = f"{hostname}:{port}"
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, hostname, path, "", parsed.query, "")).casefold()


def _backlink_key(row: SEOBacklink) -> tuple[str, str]:
    return (
        _canonical_backlink_url(row.source_url),
        _canonical_backlink_url(row.target_url or site_url()),
    )


def _unique_backlink_rows(db: Session) -> list[SEOBacklink]:
    """Return the latest record for each source/target pair."""
    rows = (
        db.execute(select(SEOBacklink).order_by(SEOBacklink.last_seen.desc()))
        .scalars()
        .all()
    )
    unique: list[SEOBacklink] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = _backlink_key(row)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _backlink_out(row: SEOBacklink, **extra: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "source_url": row.source_url,
        "target_url": row.target_url,
        "anchor_text": row.anchor_text,
        "domain": row.domain,
        "is_dofollow": row.is_dofollow,
        "notes": row.notes,
        "first_seen": row.first_seen.isoformat() if row.first_seen else None,
        "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        **extra,
    }


def list_backlinks(db: Session) -> list[dict[str, Any]]:
    return [_backlink_out(row) for row in _unique_backlink_rows(db)]


def add_backlink(
    db: Session,
    *,
    source_url: str,
    target_url: str | None = None,
    anchor_text: str | None = None,
    notes: str | None = None,
    is_dofollow: bool = True,
) -> dict[str, Any]:
    clean_source = source_url.strip()
    clean_target = (target_url or site_url()).strip()
    wanted_key = (
        _canonical_backlink_url(clean_source),
        _canonical_backlink_url(clean_target),
    )
    matches = [
        row
        for row in db.execute(
            select(SEOBacklink).order_by(SEOBacklink.last_seen.desc())
        )
        .scalars()
        .all()
        if _backlink_key(row) == wanted_key
    ]
    if matches:
        row = matches[0]
        row.source_url = clean_source
        row.target_url = clean_target
        row.domain = urlparse(clean_source).netloc.casefold()
        row.last_seen = datetime.utcnow()
        row.first_seen = min(
            (match.first_seen for match in matches if match.first_seen),
            default=row.first_seen,
        )
        if anchor_text is not None:
            row.anchor_text = anchor_text
        if notes is not None:
            row.notes = notes
        row.is_dofollow = is_dofollow
        for duplicate in matches[1:]:
            db.delete(duplicate)
        db.commit()
        db.refresh(row)
        return _backlink_out(row, created=False, duplicates_removed=len(matches) - 1)

    domain = urlparse(clean_source).netloc.casefold()
    row = SEOBacklink(
        id=str(uuid4()),
        source_url=clean_source,
        target_url=clean_target,
        anchor_text=anchor_text,
        domain=domain,
        first_seen=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        is_dofollow=is_dofollow,
        notes=notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _backlink_out(row, created=True, duplicates_removed=0)


def discover_backlinks_basic(db: Session) -> dict[str, Any]:
    """
    Lightweight free discovery: check if common directories / known partners link to us.
    Not a full backlink index — open-source alternative to paid tools.
    """
    domain = urlparse(site_url()).netloc
    if not domain:
        return {"found": 0, "message": "SITE_URL not configured"}
    # Query Bing/HTML is blocked often; instead verify self-references from sitemap social
    found = 0
    refreshed = 0
    duplicates_removed = 0
    social = get_social_settings(db)
    for label, url in social.items():
        if url and url.startswith("http"):
            try:
                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    r = client.get(url)
                    if domain in r.text:
                        result = add_backlink(
                            db,
                            source_url=url,
                            target_url=site_url(),
                            anchor_text=label,
                            notes="Discovered via social profile scan",
                        )
                        if result["created"]:
                            found += 1
                        else:
                            refreshed += 1
                        duplicates_removed += int(result["duplicates_removed"])
            except Exception:
                continue
    return {
        "found": found,
        "refreshed": refreshed,
        "duplicates_removed": duplicates_removed,
        "message": (
            f"Social scan complete: {found} new, {refreshed} refreshed, "
            f"{duplicates_removed} duplicate record(s) removed."
        ),
    }


def entity_rank_summary(db: Session) -> list[dict[str, Any]]:
    """Aggregate Search Console query rows into impression-weighted URL metrics."""
    rows = _keyword_url_rows(db, limit=5000)
    by_url: dict[str, dict[str, Any]] = {}
    for r in rows:
        u = r["url"]
        impressions = int(r.get("impressions") or 0)
        weight = impressions if impressions > 0 else 1
        if u not in by_url:
            by_url[u] = {
                "url": u,
                "entity_type": r.get("entity_type"),
                "entity_id": r.get("entity_id"),
                "average_position": 0.0,
                "impressions": 0,
                "clicks": 0,
                "ctr": 0.0,
                "_position_total": 0.0,
                "_position_weight": 0,
                "keywords": [],
            }
        by_url[u]["_position_total"] += float(r["position"]) * weight
        by_url[u]["_position_weight"] += weight
        by_url[u]["impressions"] += impressions
        by_url[u]["clicks"] += int(r.get("clicks") or 0)
        by_url[u]["keywords"].append(
            {
                "keyword": r["keyword"],
                "average_position": r["position"],
                "impressions": impressions,
                "clicks": int(r.get("clicks") or 0),
            }
        )
    for item in by_url.values():
        item["average_position"] = round(
            item.pop("_position_total") / max(item.pop("_position_weight"), 1),
            2,
        )
        item["ctr"] = (
            round(item["clicks"] / item["impressions"], 6)
            if item["impressions"] > 0
            else 0.0
        )
    return sorted(by_url.values(), key=lambda x: x["average_position"])
