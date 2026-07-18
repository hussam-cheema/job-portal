from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import env, site_url
from app.logging_config import get_logger
from app.models import BlogPost, Job, Page, SEOBacklink, SEOKeywordRank, SEOMeta, SiteSetting

logger = get_logger("jobportal.seo_tools")


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
    }


def set_social_settings(db: Session, data: dict[str, str]) -> dict[str, str]:
    mapping = {
        "facebook_url": "social_facebook",
        "youtube_url": "social_youtube",
        "x_url": "social_x",
    }
    for k, sk in mapping.items():
        if k in data:
            set_setting(db, sk, (data.get(k) or "").strip() or None)
    return get_social_settings(db)


def build_sitemap_urls(db: Session) -> list[dict[str, Any]]:
    base = site_url().rstrip("/")
    urls: list[dict[str, Any]] = [
        {"loc": f"{base}/", "changefreq": "daily", "priority": 1.0},
        {"loc": f"{base}/about", "changefreq": "monthly", "priority": 0.6},
        {"loc": f"{base}/contact", "changefreq": "monthly", "priority": 0.5},
        {"loc": f"{base}/privacy", "changefreq": "yearly", "priority": 0.3},
        {"loc": f"{base}/disclaimer", "changefreq": "yearly", "priority": 0.3},
        {"loc": f"{base}/blog", "changefreq": "daily", "priority": 0.8},
    ]
    try:
        for job in db.execute(select(Job)).scalars().all():
            urls.append(
                {
                    "loc": f"{base}/jobs/{job.slug or job.id}",
                    "lastmod": (job.updated_at or job.published_date or datetime.utcnow()).date().isoformat(),
                    "changefreq": "weekly",
                    "priority": 0.8,
                }
            )
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
        for post in db.execute(
            select(BlogPost).where(
                BlogPost.is_published.is_(True),
                (BlogPost.published_at.is_(None) | (BlogPost.published_at <= now)),
            )
        ).scalars().all():
            urls.append(
                {
                    "loc": f"{base}/blog/{post.slug}",
                    "lastmod": (post.updated_at or post.published_at or now).date().isoformat(),
                    "changefreq": "weekly",
                    "priority": 0.7,
                }
            )
    except Exception:
        logger.exception("build_sitemap_urls failed")
    return urls


def robots_txt() -> str:
    base = site_url().rstrip("/")
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
        bl_count = len(db.execute(select(SEOBacklink)).scalars().all())
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
    Pull Search Console search analytics when GOOGLE_APPLICATION_CREDENTIALS
    + GSC_SITE_URL are configured (service account with GSC access).
    """
    site = env("GSC_SITE_URL") or get_setting(db, "gsc_site_url")
    creds_path = env("GOOGLE_APPLICATION_CREDENTIALS")
    if not site or not creds_path or not os.path.exists(creds_path):
        return {
            "connected": False,
            "message": "Connect Google Search Console: set GSC_SITE_URL and GOOGLE_APPLICATION_CREDENTIALS (service account JSON path).",
            "keywords": [],
            "pages": [],
        }
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
        credentials = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
        service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
        end = datetime.utcnow().date()
        start = end - timedelta(days=28)
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["query", "page"],
            "rowLimit": 100,
        }
        resp = service.searchanalytics().query(siteUrl=site, body=body).execute()
        rows = resp.get("rows") or []

        # Clear recent snapshot ranks for this sync window (optional: keep history)
        keywords_out = []
        for row in rows:
            keys = row.get("keys") or []
            if len(keys) < 2:
                continue
            query, page = keys[0], keys[1]
            pos = float(row.get("position") or 0)
            page_num = max(1, int((pos - 1) // 10) + 1)
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
                    search_page=page_num,
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
                    "search_page": page_num,
                    "clicks": clicks,
                    "impressions": imps,
                    "ctr": ctr,
                    "entity_type": entity_type,
                }
            )
        db.commit()
        set_setting(db, "gsc_last_sync", datetime.utcnow().isoformat())
        return {
            "connected": True,
            "site": site,
            "rows": len(keywords_out),
            "keywords": keywords_out[:50],
            "message": f"Synced {len(keywords_out)} keyword/page rows from GSC (last 28 days).",
        }
    except Exception as exc:
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
        db.execute(select(SEOKeywordRank).order_by(SEOKeywordRank.recorded_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "keyword": r.keyword,
            "url": r.url,
            "position": r.position,
            "search_page": r.search_page,
            "clicks": r.clicks,
            "impressions": r.impressions,
            "ctr": r.ctr,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
        }
        for r in rows
    ]


def list_backlinks(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(select(SEOBacklink).order_by(SEOBacklink.last_seen.desc())).scalars().all()
    return [
        {
            "id": r.id,
            "source_url": r.source_url,
            "target_url": r.target_url,
            "anchor_text": r.anchor_text,
            "domain": r.domain,
            "is_dofollow": r.is_dofollow,
            "notes": r.notes,
            "first_seen": r.first_seen.isoformat() if r.first_seen else None,
            "last_seen": r.last_seen.isoformat() if r.last_seen else None,
        }
        for r in rows
    ]


def add_backlink(
    db: Session,
    *,
    source_url: str,
    target_url: str | None = None,
    anchor_text: str | None = None,
    notes: str | None = None,
    is_dofollow: bool = True,
) -> dict[str, Any]:
    domain = urlparse(source_url).netloc
    row = SEOBacklink(
        id=str(uuid4()),
        source_url=source_url.strip(),
        target_url=(target_url or site_url()).strip(),
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
    return {
        "id": row.id,
        "source_url": row.source_url,
        "target_url": row.target_url,
        "domain": row.domain,
    }


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
    social = get_social_settings(db)
    for label, url in social.items():
        if url and url.startswith("http"):
            try:
                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    r = client.get(url)
                    if domain in r.text:
                        add_backlink(
                            db,
                            source_url=url,
                            target_url=site_url(),
                            anchor_text=label,
                            notes="Discovered via social profile scan",
                        )
                        found += 1
            except Exception:
                continue
    return {
        "found": found,
        "message": f"Scanned social profiles; added {found} backlink(s). Add more manually or connect GSC.",
    }


def entity_rank_summary(db: Session) -> list[dict[str, Any]]:
    """Which job/page appears on which Google search page (from latest ranks)."""
    rows = list_keyword_ranks(db, limit=200)
    by_url: dict[str, dict[str, Any]] = {}
    for r in rows:
        u = r["url"]
        if u not in by_url:
            by_url[u] = {
                "url": u,
                "entity_type": r.get("entity_type"),
                "entity_id": r.get("entity_id"),
                "best_position": r["position"],
                "search_page": r["search_page"],
                "keywords": [],
            }
        by_url[u]["best_position"] = min(by_url[u]["best_position"], r["position"])
        by_url[u]["search_page"] = max(1, int((by_url[u]["best_position"] - 1) // 10) + 1)
        by_url[u]["keywords"].append(
            {"keyword": r["keyword"], "position": r["position"], "search_page": r["search_page"]}
        )
    return sorted(by_url.values(), key=lambda x: x["best_position"])
