from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import canonical_site_url, env, site_url
from app.logging_config import get_logger
from app.models import BlogPost, Job, Page, SEOBacklink, SEOKeywordRank, SEOMeta, SiteSetting, TaxonomyTerm
from app.utils import as_list, slugify

logger = get_logger("jobportal.seo_tools")


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
    base = canonical_site_url()
    urls: list[dict[str, Any]] = [
        {"loc": f"{base}/", "changefreq": "daily", "priority": 1.0},
        {"loc": f"{base}/about", "changefreq": "monthly", "priority": 0.6},
        {"loc": f"{base}/contact", "changefreq": "monthly", "priority": 0.5},
        {"loc": f"{base}/privacy", "changefreq": "yearly", "priority": 0.3},
        {"loc": f"{base}/disclaimer", "changefreq": "yearly", "priority": 0.3},
        {"loc": f"{base}/blog", "changefreq": "daily", "priority": 0.8},
        {"loc": f"{base}/browse", "changefreq": "daily", "priority": 0.8},
        {"loc": f"{base}/resume-builder", "changefreq": "monthly", "priority": 0.6},
        {"loc": f"{base}/cover-letter", "changefreq": "monthly", "priority": 0.6},
    ]
    try:
        jobs = db.execute(select(Job)).scalars().all()
        job_tags: set[str] = set()
        job_locations: set[str] = set()
        companies: set[str] = set()
        qualifications: set[str] = set()
        for job in jobs:
            urls.append(
                {
                    "loc": f"{base}/jobs/{job.slug or job.id}",
                    "lastmod": (job.updated_at or job.published_date or datetime.utcnow()).date().isoformat(),
                    "changefreq": "weekly",
                    "priority": 0.8,
                }
            )
            job_tags.update(value.strip() for value in as_list(job.tags) if value and value.strip())
            job_locations.update(
                value.strip()
                for value in [*as_list(job.cities), *as_list(job.provinces)]
                if value and value.strip()
            )
            if job.source and job.source.strip():
                companies.add(job.source.strip())
            if job.education_required and job.education_required.strip():
                qualifications.add(job.education_required.strip())
        categories = db.execute(
            select(TaxonomyTerm).where(
                TaxonomyTerm.kind == "category", TaxonomyTerm.is_active.is_(True)
            )
        ).scalars().all()
        for term in categories:
            urls.append({"loc": f"{base}/categories/{term.slug}", "changefreq": "weekly", "priority": 0.6})
        for value in sorted(job_tags):
            if slugify(value):
                urls.append({"loc": f"{base}/tags/{slugify(value)}", "changefreq": "weekly", "priority": 0.5})
        for value in sorted(job_locations):
            if slugify(value):
                urls.append({"loc": f"{base}/locations/{slugify(value)}", "changefreq": "weekly", "priority": 0.6})
        for value in sorted(companies):
            if slugify(value):
                urls.append({"loc": f"{base}/companies/{slugify(value)}", "changefreq": "weekly", "priority": 0.6})
        for value in sorted(qualifications):
            if slugify(value):
                urls.append({"loc": f"{base}/qualifications/{slugify(value)}", "changefreq": "weekly", "priority": 0.5})
        for page in db.execute(select(Page).where(Page.is_published.is_(True))).scalars().all():
            core_slugs = {"about", "contact", "privacy", "disclaimer"}
            path = f"/{page.slug}" if page.slug in core_slugs else f"/p/{page.slug}"
            if page.slug in core_slugs:
                continue  # already added static
            urls.append(
                {
                    "loc": f"{base}{path}",
                    "lastmod": (page.updated_at or datetime.utcnow()).date().isoformat(),
                    "changefreq": "monthly",
                    "priority": 0.5,
                }
            )
        now = datetime.utcnow()
        posts = db.execute(
            select(BlogPost).where(
                BlogPost.is_published.is_(True),
                (BlogPost.published_at.is_(None) | (BlogPost.published_at <= now)),
            )
        ).scalars().all()
        blog_categories: set[str] = set()
        blog_tags: set[str] = set()
        for post in posts:
            urls.append(
                {
                    "loc": f"{base}/blog/{post.slug}",
                    "lastmod": (post.updated_at or post.published_at or now).date().isoformat(),
                    "changefreq": "weekly",
                    "priority": 0.7,
                }
            )
            if post.category and post.category.strip():
                blog_categories.add(post.category.strip())
            blog_tags.update(value.strip() for value in as_list(post.tags) if value and value.strip())
        for value in sorted(blog_categories):
            if slugify(value):
                urls.append({"loc": f"{base}/blog/categories/{slugify(value)}", "changefreq": "weekly", "priority": 0.5})
        for value in sorted(blog_tags):
            if slugify(value):
                urls.append({"loc": f"{base}/blog/tags/{slugify(value)}", "changefreq": "weekly", "priority": 0.4})
    except Exception:
        logger.exception("build_sitemap_urls failed")
    return list({item["loc"]: item for item in urls}.values())


def _directory_values(values: list[str]) -> list[dict[str, Any]]:
    """Return stable, deduplicated public directory values with link metadata."""
    display_by_key: dict[str, str] = {}
    counts: dict[str, int] = {}
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
        for key in sorted(display_by_key, key=lambda item: display_by_key[item].casefold())
    ]


def build_site_directory(db: Session) -> dict[str, Any]:
    """Build the complete public link inventory used by Browse All and crawl tests."""
    now = datetime.utcnow()
    jobs = db.execute(
        select(Job).order_by(Job.published_date.desc(), Job.created_at.desc())
    ).scalars().all()
    posts = db.execute(
        select(BlogPost)
        .where(
            BlogPost.is_published.is_(True),
            (BlogPost.published_at.is_(None) | (BlogPost.published_at <= now)),
        )
        .order_by(BlogPost.published_at.desc(), BlogPost.created_at.desc())
    ).scalars().all()
    pages = db.execute(
        select(Page)
        .where(Page.is_published.is_(True))
        .order_by(Page.title.asc())
    ).scalars().all()
    category_terms = db.execute(
        select(TaxonomyTerm)
        .where(
            TaxonomyTerm.kind == "category",
            TaxonomyTerm.is_active.is_(True),
        )
        .order_by(TaxonomyTerm.name.asc())
    ).scalars().all()

    job_tags = [value for job in jobs for value in as_list(job.tags)]
    cities = [value for job in jobs for value in as_list(job.cities)]
    provinces = [value for job in jobs for value in as_list(job.provinces)]
    organizations = [job.source or "" for job in jobs]
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
                "published_date": job.published_date.isoformat() if job.published_date else None,
                "deadline_date": job.deadline_date.isoformat() if job.deadline_date else None,
                "applications_closed": bool(
                    job.deadline_date and job.deadline_date.date() < now.date()
                ),
                "organization": (job.source or "").strip() or None,
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
                "published_at": post.published_at.isoformat() if post.published_at else None,
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
                "path": (
                    f"/{page.slug}"
                    if page.slug in {"about", "contact", "privacy", "disclaimer"}
                    else f"/p/{page.slug}"
                ),
            }
            for page in pages
        ],
        "taxonomies": {
            "job_categories": [
                {"name": term.name, "slug": term.slug, "count": 0}
                for term in category_terms
            ],
            "job_tags": _directory_values(job_tags),
            "cities": _directory_values(cities),
            "provinces": _directory_values(provinces),
            "organizations": _directory_values(organizations),
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
            params = {"url": target, "category": "performance", "strategy": "mobile", "key": api_key}
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
                "fcp_ms": (audits.get("first-contentful-paint") or {}).get("numericValue"),
                "lcp_ms": (audits.get("largest-contentful-paint") or {}).get("numericValue"),
                "cls": (audits.get("cumulative-layout-shift") or {}).get("numericValue"),
                "tbt_ms": (audits.get("total-blocking-time") or {}).get("numericValue"),
            }
        except Exception as exc:
            logger.exception("pagespeed api failed")
            return {"score": 0, "source": "pagespeed_error", "error": str(exc), "url": target}

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
        jobs = db.execute(select(Job)).scalars().all()
        pages = db.execute(select(Page)).scalars().all()
        metas = db.execute(select(SEOMeta)).scalars().all()
        bl_count = len(_unique_backlink_rows(db))
        scores = [m.seo_score for m in metas if m.seo_score is not None]
        avg_seo = sum(scores) / len(scores) if scores else 40
        coverage = (len(metas) / max(len(jobs) + len(pages), 1)) * 100
        bl_component = min(30, bl_count * 2)
        score = round(min(100, avg_seo * 0.5 + coverage * 0.3 + bl_component), 1)
        return {
            "score": score,
            "avg_onpage_seo": round(avg_seo, 1),
            "seo_coverage_pct": round(coverage, 1),
            "backlinks": bl_count,
            "jobs": len(jobs),
            "pages": len(pages),
            "method": "composite_onpage_backlinks",
        }
    except Exception:
        logger.exception("authority_score failed")
        return {"score": 0, "method": "error"}


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
        service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
        # Use an exact 28-day window and avoid today's still-changing data.
        end = datetime.utcnow().date() - timedelta(days=1)
        start = end - timedelta(days=27)
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["query", "page"],
            "rowLimit": 100,
        }
        resp = service.searchanalytics().query(siteUrl=site, body=body).execute()
        rows = resp.get("rows") or []

        # The dashboard represents the latest 28-day snapshot. Replace the
        # previous snapshot atomically so repeated syncs cannot append the same
        # keyword/URL rows indefinitely.
        db.execute(delete(SEOKeywordRank))
        keywords_out = []
        seen_pairs: set[tuple[str, str]] = set()
        for row in rows:
            keys = row.get("keys") or []
            if len(keys) < 2:
                continue
            query, page = keys[0], keys[1]
            pair = (str(query).strip().casefold(), str(page).strip().rstrip("/").casefold())
            if not pair[0] or not pair[1] or pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            pos = float(row.get("position") or 0)
            clicks = int(row.get("clicks") or 0)
            imps = int(row.get("impressions") or 0)
            ctr = float(row.get("ctr") or 0)
            entity_type, entity_id = _match_entity(db, page)
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
        set_setting(db, "gsc_last_sync", datetime.utcnow().isoformat())
        set_setting(db, "gsc_period_start", start.isoformat())
        set_setting(db, "gsc_period_end", end.isoformat())
        return {
            "connected": True,
            "site": site,
            "rows": len(keywords_out),
            "keywords": keywords_out[:50],
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "message": (
                f"Synced {len(keywords_out)} query/URL rows from Google Search Console "
                f"for {start.isoformat()} to {end.isoformat()}."
            ),
        }
    except Exception as exc:
        db.rollback()
        logger.exception("gsc sync failed")
        return {"connected": False, "message": f"GSC sync failed: {exc}", "keywords": [], "pages": []}


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
            page = db.execute(select(Page).where(Page.slug == slug)).scalar_one_or_none()
            if page:
                return "page", page.id
    except Exception:
        pass
    return None, None


def list_keyword_ranks(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(SEOKeywordRank)
            .order_by(SEOKeywordRank.recorded_at.desc())
            .limit(max(limit * 5, 200))
        )
        .scalars()
        .all()
    )
    unique_rows: list[SEOKeywordRank] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.keyword.strip().casefold(), row.url.strip().rstrip("/").casefold())
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
        if len(unique_rows) >= limit:
            break
    return [
        {
            "id": r.id,
            "keyword": r.keyword,
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


def _canonical_backlink_url(value: str | None) -> str:
    """Normalize inconsequential URL differences for backlink identity checks."""
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    scheme = parsed.scheme.casefold()
    hostname = (parsed.hostname or "").casefold()
    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
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
    rows = db.execute(select(SEOBacklink).order_by(SEOBacklink.last_seen.desc())).scalars().all()
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
        ).scalars().all()
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
    rows = list_keyword_ranks(db, limit=200)
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
