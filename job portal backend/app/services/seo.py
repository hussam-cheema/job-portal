from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import canonical_site_url, cfg, site_name
from app.logging_config import get_logger
from app.models import BlogPost, Job, Page, SEOMeta, SEOMetric, ToolCategory, ToolPage
from app.page_types import public_page_path
from app.utils import strip_html

logger = get_logger("jobportal.seo")


def _clean_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned = (str(item).strip() for item in value if item is not None)
    return list(dict.fromkeys(item for item in cleaned if item))


def _job_locations(job: Job) -> list[dict[str, Any]]:
    cities = _clean_values(job.cities)
    provinces = _clean_values(job.provinces)

    if not cities and not provinces:
        return [
            {
                "@type": "Place",
                "address": {"@type": "PostalAddress", "addressCountry": "PK"},
            }
        ]

    if cities:
        region = provinces[0] if len(provinces) == 1 else None
        result = []
        for city in cities:
            address: dict[str, Any] = {
                "@type": "PostalAddress",
                "addressLocality": city,
                "addressCountry": "PK",
            }
            if region:
                address["addressRegion"] = region
            result.append({"@type": "Place", "address": address})
        return result

    return [
        {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressRegion": province,
                "addressCountry": "PK",
            },
        }
        for province in provinces
    ]


def build_job_structured_data(job: Job) -> dict[str, Any]:
    """Return truthful JobPosting JSON-LD without nulls, empty values, or guesses."""
    canonical = _canonical(f"/jobs/{job.slug}")
    organization = (job.source or "").strip() or site_name()
    structured: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": job.title,
        "description": (job.description or "").strip() or job.title,
        "hiringOrganization": {"@type": "Organization", "name": organization},
        "jobLocation": _job_locations(job),
        "identifier": {
            "@type": "PropertyValue",
            "name": organization,
            "value": job.id,
        },
        "url": canonical,
    }
    if job.published_date:
        structured["datePosted"] = job.published_date.isoformat()
    if job.deadline_date:
        structured["validThrough"] = job.deadline_date.isoformat()
    if job.education_required and job.education_required.strip():
        structured["educationRequirements"] = job.education_required.strip()
    if job.experience_required and job.experience_required.strip():
        structured["experienceRequirements"] = job.experience_required.strip()
    skills = _clean_values(job.skills)
    if skills:
        structured["skills"] = ", ".join(skills)
    tags = _clean_values(job.tags)
    if tags:
        structured["industry"] = tags[0]
    return structured


def _canonical(path: str) -> str:
    base = canonical_site_url()
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"


def upsert_job_seo(db: Session, job: Job, seo_override: dict | None = None) -> SEOMeta:
    try:
        from app.services.yoast import analyze_yoast

        existing = db.execute(
            select(SEOMeta).where(
                SEOMeta.entity_type == "job", SEOMeta.entity_id == job.id
            )
        ).scalar_one_or_none()
        ov = seo_override or {}

        auto_title = f"{job.title} | {site_name()}"
        auto_desc = strip_html(job.description or "", 160)
        if not auto_desc:
            cities = ", ".join(job.cities or []) if isinstance(job.cities, list) else ""
            auto_desc = (
                f"{job.title} job in Pakistan{(' — ' + cities) if cities else ''}."
            )
        keywords_parts = []
        if job.keywords:
            keywords_parts.append(strip_html(job.keywords, 300))
        if isinstance(job.tags, list):
            keywords_parts.extend(str(t) for t in job.tags)
        if isinstance(job.skills, list):
            keywords_parts.extend(str(s) for s in job.skills[:10])
        keywords_parts.extend(["Pakistan jobs", job.job_type or "", site_name()])
        auto_kw = ", ".join(dict.fromkeys([k for k in keywords_parts if k]))

        title = (ov.get("meta_title") or auto_title)[:300]
        desc = (ov.get("meta_description") or auto_desc)[:500]
        keywords = ov.get("meta_keywords") or auto_kw
        focus = (ov.get("focus_keyword") or "").strip() or None

        path = f"/jobs/{job.slug}"
        analysis = analyze_yoast(
            title=job.title,
            content_html=job.description or "",
            meta_title=title,
            meta_description=desc,
            focus_keyword=focus,
            slug=job.slug,
        )
        structured = build_job_structured_data(job)

        if existing:
            existing.slug = job.slug
            existing.meta_title = title
            existing.meta_description = desc
            existing.meta_keywords = keywords
            existing.focus_keyword = focus
            existing.seo_score = analysis["seo_score"]
            existing.readability_score = analysis["readability_score"]
            existing.analysis = analysis
            existing.og_title = title
            existing.og_description = desc
            existing.canonical_url = _canonical(path)
            existing.robots = str(cfg("seo", "default_robots", default="index,follow"))
            existing.structured_data = structured
            existing.h1 = job.title[:300]
            existing.updated_at = datetime.utcnow()
            db.add(existing)
            return existing

        row = SEOMeta(
            id=str(uuid4()),
            entity_type="job",
            entity_id=job.id,
            slug=job.slug,
            meta_title=title,
            meta_description=desc,
            meta_keywords=keywords,
            focus_keyword=focus,
            seo_score=analysis["seo_score"],
            readability_score=analysis["readability_score"],
            analysis=analysis,
            og_title=title,
            og_description=desc,
            og_image=None,
            canonical_url=_canonical(path),
            robots=str(cfg("seo", "default_robots", default="index,follow")),
            structured_data=structured,
            h1=job.title[:300],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        return row
    except Exception:
        logger.exception("upsert_job_seo failed job_id=%s", getattr(job, "id", None))
        raise


def upsert_page_seo(
    db: Session, page: Page, seo_override: dict | None = None
) -> SEOMeta:
    try:
        from app.services.yoast import analyze_yoast

        existing = db.execute(
            select(SEOMeta).where(
                SEOMeta.entity_type == "page", SEOMeta.entity_id == page.id
            )
        ).scalar_one_or_none()
        ov = seo_override or {}
        auto_title = f"{page.title} | {site_name()}"
        auto_desc = (
            strip_html(page.content or "", 160) or f"{page.title} — {site_name()}"
        )
        path = public_page_path(page.page_type, page.slug)
        if existing and seo_override is None:
            title = (existing.meta_title or auto_title)[:300]
            desc = (existing.meta_description or auto_desc)[:500]
            keywords = existing.meta_keywords or f"{page.title}, {site_name()}, Pakistan jobs"
            focus = existing.focus_keyword
        else:
            title = (ov.get("meta_title") or auto_title)[:300]
            desc = (ov.get("meta_description") or auto_desc)[:500]
            keywords = (
                ov.get("meta_keywords") or f"{page.title}, {site_name()}, Pakistan jobs"
            )
            focus = (ov.get("focus_keyword") or "").strip() or None
        analysis = analyze_yoast(
            title=page.title,
            content_html=page.content or "",
            meta_title=title,
            meta_description=desc,
            focus_keyword=focus,
            slug=page.slug,
        )
        structured = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": page.title,
            "description": desc,
            "url": _canonical(path),
            "isPartOf": {
                "@type": "WebSite",
                "name": site_name(),
                "url": canonical_site_url(),
            },
        }
        if existing:
            existing.slug = page.slug
            existing.meta_title = title
            existing.meta_description = desc
            existing.meta_keywords = keywords
            existing.focus_keyword = focus
            existing.seo_score = analysis["seo_score"]
            existing.readability_score = analysis["readability_score"]
            existing.analysis = analysis
            existing.og_title = existing.og_title if seo_override is None else title
            existing.og_description = (
                existing.og_description if seo_override is None else desc
            )
            existing.canonical_url = _canonical(path)
            existing.robots = str(cfg("seo", "default_robots", default="index,follow"))
            existing.structured_data = structured
            existing.h1 = page.title[:300]
            existing.updated_at = datetime.utcnow()
            db.add(existing)
            return existing

        row = SEOMeta(
            id=str(uuid4()),
            entity_type="page",
            entity_id=page.id,
            slug=page.slug,
            meta_title=title,
            meta_description=desc,
            meta_keywords=keywords,
            focus_keyword=focus,
            seo_score=analysis["seo_score"],
            readability_score=analysis["readability_score"],
            analysis=analysis,
            og_title=title,
            og_description=desc,
            canonical_url=_canonical(path),
            robots=str(cfg("seo", "default_robots", default="index,follow")),
            structured_data=structured,
            h1=page.title[:300],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        return row
    except Exception:
        logger.exception("upsert_page_seo failed page_id=%s", getattr(page, "id", None))
        raise


def delete_seo(db: Session, entity_type: str, entity_id: str) -> None:
    try:
        db.query(SEOMeta).filter(
            SEOMeta.entity_type == entity_type, SEOMeta.entity_id == entity_id
        ).delete()
    except Exception:
        logger.exception("delete_seo failed %s %s", entity_type, entity_id)


def upsert_tool_seo(
    db: Session,
    entity: ToolCategory | ToolPage,
    *,
    entity_type: str,
    path: str,
    seo_override: dict | None = None,
) -> SEOMeta:
    """Create or update SEO metadata for a tool category or tool page."""
    if entity_type not in {"tool_category", "tool"}:
        raise ValueError("Unsupported tool SEO entity type")
    from app.services.yoast import analyze_yoast

    existing = db.execute(
        select(SEOMeta).where(
            SEOMeta.entity_type == entity_type,
            SEOMeta.entity_id == entity.id,
        )
    ).scalar_one_or_none()
    ov = seo_override or {}
    auto_title = f"{entity.title} | {site_name()}"
    auto_desc = strip_html(entity.content or "", 160) or f"Use {entity.title} on {site_name()}."
    if existing and seo_override is None:
        title = (existing.meta_title or auto_title)[:300]
        desc = (existing.meta_description or auto_desc)[:500]
        keywords = existing.meta_keywords or f"{entity.title}, Pakistan tools, {site_name()}"
        focus = existing.focus_keyword
    else:
        title = (ov.get("meta_title") or auto_title)[:300]
        desc = (ov.get("meta_description") or auto_desc)[:500]
        keywords = ov.get("meta_keywords") or f"{entity.title}, Pakistan tools, {site_name()}"
        focus = (ov.get("focus_keyword") or "").strip() or None
    analysis = analyze_yoast(
        title=entity.title,
        content_html=entity.content or "",
        meta_title=title,
        meta_description=desc,
        focus_keyword=focus,
        slug=entity.slug,
    )
    structured = {
        "@context": "https://schema.org",
        "@type": "WebApplication" if entity_type == "tool" else "CollectionPage",
        "name": entity.title,
        "description": desc,
        "url": _canonical(path),
        "isPartOf": {
            "@type": "WebSite",
            "name": site_name(),
            "url": canonical_site_url(),
        },
    }
    values = {
        "slug": entity.slug,
        "meta_title": title,
        "meta_description": desc,
        "meta_keywords": keywords,
        "focus_keyword": focus,
        "seo_score": analysis["seo_score"],
        "readability_score": analysis["readability_score"],
        "analysis": analysis,
        "og_title": title,
        "og_description": desc,
        "canonical_url": _canonical(path),
        "robots": str(cfg("seo", "default_robots", default="index,follow")),
        "structured_data": structured,
        "h1": entity.title[:300],
        "updated_at": datetime.utcnow(),
    }
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        db.add(existing)
        return existing
    row = SEOMeta(
        id=str(uuid4()),
        entity_type=entity_type,
        entity_id=entity.id,
        created_at=datetime.utcnow(),
        **values,
    )
    db.add(row)
    return row


def upsert_blog_seo(
    db: Session, post: BlogPost, seo_override: dict | None = None
) -> SEOMeta:
    try:
        from app.services.yoast import analyze_yoast

        existing = db.execute(
            select(SEOMeta).where(
                SEOMeta.entity_type == "blog", SEOMeta.entity_id == post.id
            )
        ).scalar_one_or_none()
        ov = seo_override or {}
        auto_title = f"{post.title} | {site_name()}"
        auto_desc = (post.excerpt or strip_html(post.content or "", 160)).strip()
        auto_desc = auto_desc or f"{post.title} — {site_name()}"
        title = (ov.get("meta_title") or auto_title)[:300]
        desc = (ov.get("meta_description") or auto_desc)[:500]
        keywords = ov.get("meta_keywords") or ", ".join(
            dict.fromkeys(
                [post.category or "", *(post.tags or []), "Pakistan jobs", site_name()]
            )
        ).strip(", ")
        focus = (ov.get("focus_keyword") or "").strip() or None
        path = f"/blog/{post.slug}"
        analysis = analyze_yoast(
            title=post.title,
            content_html=post.content or "",
            meta_title=title,
            meta_description=desc,
            focus_keyword=focus,
            slug=post.slug,
        )
        structured = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": post.title,
            "description": desc,
            "articleBody": strip_html(post.content or "", 10000),
            "datePublished": post.published_at.isoformat()
            if post.published_at
            else None,
            "dateModified": post.updated_at.isoformat() if post.updated_at else None,
            "author": {"@type": "Person", "name": post.author or site_name()},
            "mainEntityOfPage": _canonical(path),
            "url": _canonical(path),
            "isPartOf": {
                "@type": "WebSite",
                "name": site_name(),
                "url": canonical_site_url(),
            },
        }
        values = {
            "slug": post.slug,
            "meta_title": title,
            "meta_description": desc,
            "meta_keywords": keywords,
            "focus_keyword": focus,
            "seo_score": analysis["seo_score"],
            "readability_score": analysis["readability_score"],
            "analysis": analysis,
            "og_title": title,
            "og_description": desc,
            "canonical_url": _canonical(path),
            "robots": str(cfg("seo", "default_robots", default="index,follow")),
            "structured_data": structured,
            "h1": post.title[:300],
            "updated_at": datetime.utcnow(),
        }
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            db.add(existing)
            return existing
        row = SEOMeta(
            id=str(uuid4()),
            entity_type="blog",
            entity_id=post.id,
            created_at=datetime.utcnow(),
            **values,
        )
        db.add(row)
        return row
    except Exception:
        logger.exception("upsert_blog_seo failed post_id=%s", getattr(post, "id", None))
        raise


def build_seo_dashboard(db: Session) -> dict[str, Any]:
    try:
        total_jobs = db.execute(select(func.count()).select_from(Job)).scalar() or 0
        total_pages = db.execute(select(func.count()).select_from(Page)).scalar() or 0
        jobs_seo = (
            db.execute(
                select(func.count())
                .select_from(SEOMeta)
                .where(SEOMeta.entity_type == "job")
            ).scalar()
            or 0
        )
        pages_seo = (
            db.execute(
                select(func.count())
                .select_from(SEOMeta)
                .where(SEOMeta.entity_type == "page")
            ).scalar()
            or 0
        )

        issues: list[str] = []
        # On-page checks
        jobs = db.execute(
            select(Job.title, Job.description, Job.keywords, Job.tags, Job.slug)
        ).all()
        missing_desc = 0
        short_title = 0
        no_keywords = 0
        no_slug = 0
        for j in jobs:
            if not j.description or len(strip_html(j.description)) < 50:
                missing_desc += 1
            if not j.title or len(j.title) < 10:
                short_title += 1
            if not j.keywords and not (j.tags or []):
                no_keywords += 1
            if not j.slug:
                no_slug += 1
        if missing_desc:
            issues.append(f"{missing_desc} job(s) have thin/missing descriptions")
        if short_title:
            issues.append(f"{short_title} job(s) have short titles")
        if no_keywords:
            issues.append(f"{no_keywords} job(s) missing keywords/tags")
        if jobs_seo < total_jobs:
            issues.append(f"{total_jobs - jobs_seo} job(s) missing SEO meta rows")
        if pages_seo < total_pages:
            issues.append(f"{total_pages - pages_seo} page(s) missing SEO meta rows")

        coverage = round((jobs_seo / total_jobs) * 100, 1) if total_jobs else 100.0
        on_page = {
            "seo_coverage_pct": coverage,
            "jobs_with_meta_title": jobs_seo,
            "jobs_with_canonical": jobs_seo,
            "jobs_with_structured_data": jobs_seo,
            "thin_descriptions": missing_desc,
            "avg_title_length": round(
                sum(len(j.title or "") for j in jobs) / total_jobs, 1
            )
            if total_jobs
            else 0,
            "avg_description_length": round(
                sum(len(strip_html(j.description or "")) for j in jobs) / total_jobs, 1
            )
            if total_jobs
            else 0,
        }
        off_page = {
            "indexed_urls_estimate": total_jobs + total_pages + 4,
            "sitemap_entries": total_jobs + total_pages,
            "backlinks": "N/A (connect Search Console)",
            "domain_authority": "N/A",
            "referring_domains": "N/A",
            "social_signals": "N/A",
        }
        # Simple performance snapshot from DB
        performance = {
            "total_jobs": total_jobs,
            "total_pages": total_pages,
            "api_health": "ok",
            "avg_response_hint_ms": 120,
            "lighthouse_performance": "Run Lighthouse in browser for live scores",
            "core_web_vitals": {
                "lcp": "measure client-side",
                "cls": "measure client-side",
                "inp": "measure client-side",
            },
        }

        # Persist snapshot metrics
        now = datetime.utcnow()
        for label, value, mtype, unit in [
            ("SEO coverage %", coverage, "on_page", "%"),
            ("Total jobs", float(total_jobs), "performance", "count"),
            ("Total pages", float(total_pages), "performance", "count"),
            ("Thin descriptions", float(missing_desc), "on_page", "count"),
        ]:
            db.add(
                SEOMetric(
                    id=str(uuid4()),
                    metric_type=mtype,
                    label=label,
                    value=value,
                    unit=unit,
                    details=None,
                    recorded_at=now,
                )
            )
        db.commit()

        recent = (
            db.execute(
                select(SEOMetric).order_by(SEOMetric.recorded_at.desc()).limit(40)
            )
            .scalars()
            .all()
        )
        metrics = [
            {
                "id": m.id,
                "metric_type": m.metric_type,
                "label": m.label,
                "value": m.value,
                "unit": m.unit,
                "recorded_at": m.recorded_at.isoformat() if m.recorded_at else None,
            }
            for m in recent
        ]

        return {
            "on_page": on_page,
            "off_page": off_page,
            "performance": performance,
            "jobs_with_seo": jobs_seo,
            "pages_with_seo": pages_seo,
            "total_jobs": total_jobs,
            "total_pages": total_pages,
            "issues": issues,
            "metrics": metrics,
        }
    except Exception:
        logger.exception("build_seo_dashboard failed")
        return {
            "on_page": {},
            "off_page": {},
            "performance": {},
            "jobs_with_seo": 0,
            "pages_with_seo": 0,
            "total_jobs": 0,
            "total_pages": 0,
            "issues": ["Failed to compute SEO dashboard"],
            "metrics": [],
        }


def get_seo_for_entity(
    db: Session, entity_type: str, entity_id: str
) -> Optional[SEOMeta]:
    try:
        return db.execute(
            select(SEOMeta).where(
                SEOMeta.entity_type == entity_type, SEOMeta.entity_id == entity_id
            )
        ).scalar_one_or_none()
    except Exception:
        logger.exception("get_seo_for_entity failed")
        return None
