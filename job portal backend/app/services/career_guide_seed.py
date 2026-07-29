from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.career_guides import CAREER_GUIDES
from app.models import BlogPost, SiteSetting
from app.services.seo import upsert_blog_seo


CAREER_GUIDES_MARKER = "career_guides_2026_v1_published"


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
