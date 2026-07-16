from __future__ import annotations

import os
from datetime import datetime, timedelta
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import func, select

from app.auth import ensure_admin_user
from app.database import SessionLocal
from app.logging_config import get_logger
from app.models import Job, JobQnA, Page, SiteSetting
from app.services.seo import upsert_job_seo, upsert_page_seo
from app.services.taxonomy import ensure_default_taxonomy
from app.utils import slugify

logger = get_logger("jobportal.seed")

DISCLAIMER_HTML = (
    "<p><strong>PakistanJobs</strong> aggregates job advertisements from Pakistan's leading "
    "newspapers, including <em>Daily Jang</em>, <em>Express</em>, <em>Nawa-i-Waqt</em>, "
    "<em>The News</em>, <em>Dawn</em>, <em>The Nation</em>, and others, as well as from the "
    "careers and jobs pages of government institutions and private companies. Our goal is to "
    "support job seekers across cities such as Karachi, Lahore, Rawalpindi, Islamabad, Peshawar, "
    "and beyond by bringing together newspaper listings and both private- and public-sector job "
    "postings in one place. This service is offered in good faith as a public resource, and we "
    "are not responsible for any advertisement that is inaccurate, misrepresented, or misleading.</p>"
)

DEFAULT_PAGES = [
    (
        "about",
        "About Us",
        "<p><strong>PakistanJobs</strong> is a modern job portal for Pakistan. Browse curated "
        "government and private openings with city, skills, and category tags.</p>"
        "<p>Job pages include commonly asked questions and answers sourced from closely matched "
        "YouTube videos when verified Q&amp;A is available.</p>"
        "<p>Whether you are preparing for private-sector roles or public-sector competitive exams, "
        "PakistanJobs helps you discover opportunities faster.</p>",
    ),
    (
        "privacy",
        "Privacy Policy",
        "<p>PakistanJobs displays publicly available job advertisements collected from third-party "
        "sources, including newspapers, company sites, and government portals.</p>"
        "<p>We do not sell personal data. If you contact us, we use your message only to respond. "
        "Server logs may include standard technical data for security and reliability.</p>"
        "<p>Job listings may include employer contact details published by the source. Use those "
        "details only for legitimate applications.</p>",
    ),
    (
        "contact",
        "Contact Us",
        "<p>Questions, partnership ideas, or corrections to a listing? Send a message below. "
        "PakistanJobs does not process job applications.</p>",
    ),
    ("disclaimer", "Disclaimer", DISCLAIMER_HTML),
]


def ensure_default_pages(db) -> list[Page]:
    """Create missing core CMS pages without overwriting administrator edits."""
    created: list[Page] = []
    for slug, title, content in DEFAULT_PAGES:
        exists = db.execute(select(Page).where(Page.slug == slug)).scalar_one_or_none()
        if exists:
            continue
        page = Page(
            id=str(uuid4()),
            slug=slug,
            title=title,
            content=content,
            is_published=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(page)
        upsert_page_seo(db, page)
        created.append(page)
    return created


def sync_local_core_pages_once(db) -> list[Page]:
    """Apply the current production-page snapshot to the local DB exactly once."""
    site_host = (urlparse(os.getenv("SITE_URL", "http://localhost:3000")).hostname or "").lower()
    if site_host not in {"localhost", "127.0.0.1", "frontend"}:
        return []
    marker_key = "local_core_pages_synced_from_production_v1"
    if db.get(SiteSetting, marker_key):
        return []

    changed: list[Page] = []
    for slug, title, content in DEFAULT_PAGES:
        page = db.execute(select(Page).where(Page.slug == slug)).scalar_one_or_none()
        if not page:
            continue
        page.title = title
        page.content = content
        page.is_published = True
        page.updated_at = datetime.utcnow()
        upsert_page_seo(db, page)
        changed.append(page)
    db.add(
        SiteSetting(
            key=marker_key,
            value="true",
            updated_at=datetime.utcnow(),
        )
    )
    db.flush()
    return changed

SEED_JOBS = [
    {
        "title": "Senior Software Engineer — Backend",
        "description": "<p>Build scalable APIs and services for enterprise clients across Pakistan.</p><ul><li>Python / FastAPI</li><li>PostgreSQL</li><li>AWS</li></ul>",
        "source": "Systems Limited",
        "cities": ["Lahore"],
        "job_type": "private",
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "tags": ["Software Engineering"],
        "salary_range": "PKR 250,000 – 400,000",
        "experience_required": "4 year(s)",
        "education_required": "BS Computer Science",
        "days_ago": 2,
        "deadline_days": 20,
    },
    {
        "title": "Assistant Director (IT)",
        "description": "<p>Federal government IT role. Competitive exam based recruitment.</p>",
        "source": "FPSC",
        "cities": ["Islamabad"],
        "job_type": "government",
        "skills": ["IT Management", "Networking"],
        "tags": ["Government", "IT"],
        "salary_range": "BPS-17",
        "experience_required": "2 year(s)",
        "education_required": "Master's in CS / IT",
        "days_ago": 5,
        "deadline_days": 14,
    },
    {
        "title": "Frontend Developer (React / Next.js)",
        "description": "<p>Ship polished product UI for global clients.</p>",
        "source": "10Pearls",
        "cities": ["Karachi"],
        "job_type": "private",
        "skills": ["React", "Next.js", "TypeScript"],
        "tags": ["Software Engineering"],
        "salary_range": "PKR 180,000 – 300,000",
        "experience_required": "3 year(s)",
        "education_required": "BS CS",
        "days_ago": 1,
        "deadline_days": 30,
    },
]


def seed_if_empty() -> None:
    db = SessionLocal()
    try:
        ensure_admin_user(db)

        ensure_default_pages(db)
        sync_local_core_pages_once(db)
        ensure_default_taxonomy(db)

        count = db.execute(select(func.count()).select_from(Job)).scalar() or 0
        if count > 0:
            db.commit()
            logger.info("seed skipped — jobs already present count=%s", count)
            return

        now = datetime.utcnow()
        for item in SEED_JOBS:
            job_id = str(uuid4())
            published = now - timedelta(days=item["days_ago"])
            deadline = now + timedelta(days=item["deadline_days"])
            title = item["title"]
            job = Job(
                id=job_id,
                slug=slugify(title),
                title=title,
                description=item["description"],
                published_date=published,
                deadline_date=deadline,
                salary_range=item.get("salary_range"),
                source=item.get("source"),
                reference_url=None,
                application_url=None,
                experience_required=item.get("experience_required"),
                education_required=item.get("education_required"),
                skills=item.get("skills") or [],
                job_type=item.get("job_type"),
                cities=item.get("cities") or [],
                tags=item.get("tags") or [],
                keywords=", ".join(item.get("tags") or []),
                created_at=published,
                updated_at=published,
            )
            db.add(job)
            upsert_job_seo(db, job)
            db.add(
                JobQnA(
                    id=str(uuid4()),
                    job_id=job_id,
                    question="What experience is required?",
                    answer=item.get("experience_required") or "See job description.",
                    source="seed",
                    youtube_url="https://www.youtube.com/results?search_query="
                    + title.replace(" ", "+")
                    + "+interview",
                    youtube_title=f"Interview tips — {title}",
                    created_at=now,
                )
            )
            db.add(
                JobQnA(
                    id=str(uuid4()),
                    job_id=job_id,
                    question="How should I prepare?",
                    answer="Review the listed skills and practice common interview questions for this role.",
                    source="seed",
                    youtube_url=None,
                    youtube_title=None,
                    created_at=now,
                )
            )

        db.flush()
        ensure_default_taxonomy(db)

        db.commit()
        logger.info("seeded sample jobs count=%s", len(SEED_JOBS))
    except Exception:
        db.rollback()
        logger.exception("seed_if_empty failed")
        raise
    finally:
        db.close()
