from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select

from app.auth import ensure_admin_user
from app.database import SessionLocal
from app.logging_config import get_logger
from app.models import Job, JobQnA, Page
from app.services.seo import upsert_job_seo, upsert_page_seo
from app.utils import slugify

logger = get_logger("jobportal.seed")

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

        # Default CMS pages
        for slug, title, content in [
            ("about", "About Us", "<p>PakJobs helps Pakistanis discover government and private job openings.</p>"),
            ("privacy", "Privacy Policy", "<p>We respect your privacy. Contact messages are only used to respond to your inquiry.</p>"),
            ("contact", "Contact Us", "<p>Use the contact form or email us. We do not process job applications.</p>"),
        ]:
            exists = db.execute(select(Page).where(Page.slug == slug)).scalar_one_or_none()
            if not exists:
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

        db.commit()
        logger.info("seeded sample jobs count=%s", len(SEED_JOBS))
    except Exception:
        db.rollback()
        logger.exception("seed_if_empty failed")
        raise
    finally:
        db.close()
