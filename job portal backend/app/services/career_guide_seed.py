from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.career_guide_enrichments import CAREER_GUIDE_ENRICHMENTS
from app.content.career_guides import CAREER_GUIDES
from app.models import BlogPost, SiteSetting
from app.services.seo import upsert_blog_seo


CAREER_GUIDES_MARKER = "career_guides_2026_v1_published"
CAREER_GUIDES_ENRICHMENT_MARKER = "career_guides_2026_v2_enriched"


def publish_career_guides_once(db: Session) -> list[BlogPost]:
    """Publish the editorial career-guide library once, without restoring deleted posts."""
    if db.get(SiteSetting, CAREER_GUIDES_MARKER):
        return []

    published: list[BlogPost] = []
    now = datetime.utcnow()
    for index, guide in enumerate(CAREER_GUIDES):
        existing = db.execute(
            select(BlogPost).where(BlogPost.slug == guide["slug"])
        ).scalar_one_or_none()
        if existing:
            continue

        timestamp = now - timedelta(minutes=index)
        post = BlogPost(
            id=str(uuid4()),
            slug=guide["slug"],
            title=guide["title"],
            excerpt=guide["excerpt"],
            content=guide["content"],
            author=guide["author"],
            category=guide["category"],
            tags=guide["tags"],
            is_published=True,
            published_at=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(post)
        db.flush()
        upsert_blog_seo(
            db,
            post,
            {
                "focus_keyword": guide["focus_keyword"],
                "meta_title": guide["meta_title"],
                "meta_description": guide["meta_description"],
                "meta_keywords": guide["meta_keywords"],
            },
        )
        published.append(post)

    db.add(
        SiteSetting(
            key=CAREER_GUIDES_MARKER,
            value="true",
            updated_at=now,
        )
    )
    return published


def enrich_career_guides_once(db: Session) -> list[BlogPost]:
    """Apply the reviewed long-form expansion once without overwriting future CMS edits."""
    if db.get(SiteSetting, CAREER_GUIDES_ENRICHMENT_MARKER):
        return []

    guides_by_slug = {guide["slug"]: guide for guide in CAREER_GUIDES}
    updated: list[BlogPost] = []
    now = datetime.utcnow()

    for slug, enrichment in CAREER_GUIDE_ENRICHMENTS.items():
        guide = guides_by_slug.get(slug)
        if not guide:
            continue

        post = db.execute(
            select(BlogPost).where(BlogPost.slug == slug)
        ).scalar_one_or_none()
        if not post:
            continue

        post.excerpt = enrichment["excerpt"]
        post.content = f"{guide['content'].rstrip()}\n\n{enrichment['content'].strip()}\n"
        post.updated_at = now
        db.add(post)
        db.flush()
        upsert_blog_seo(
            db,
            post,
            {
                "focus_keyword": enrichment["focus_keyword"],
                "meta_title": enrichment["meta_title"],
                "meta_description": enrichment["meta_description"],
                "meta_keywords": enrichment["meta_keywords"],
            },
        )
        updated.append(post)

    db.add(
        SiteSetting(
            key=CAREER_GUIDES_ENRICHMENT_MARKER,
            value="true",
            updated_at=now,
        )
    )
    return updated
