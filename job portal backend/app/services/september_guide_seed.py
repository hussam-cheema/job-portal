from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.september_guides import SEPTEMBER_GUIDES
from app.models import BlogPost, SiteSetting
from app.services.seo import upsert_blog_seo

MARKER = "september_policy_guides_2026_v1_published"


def publish_september_guides_once(db: Session) -> list[BlogPost]:
    """Publish once in the caller's transaction; preserve CMS edits and deletions."""
    if db.get(SiteSetting, MARKER):
        return []
    now = datetime.utcnow()
    created = []
    for guide in SEPTEMBER_GUIDES:
        if db.execute(select(BlogPost.id).where(BlogPost.slug == guide["slug"])).first():
            continue
        post = BlogPost(id=str(uuid4()), **{key: guide[key] for key in
            ("slug", "title", "excerpt", "content", "author", "category", "tags")},
            is_published=True, published_at=now, created_at=now, updated_at=now)
        db.add(post)
        db.flush()
        seo = upsert_blog_seo(db, post, {key: guide[key] for key in
            ("focus_keyword", "meta_title", "meta_description", "meta_keywords")})
        if seo is None:
            raise RuntimeError(f"Could not create SEO for {guide['slug']}")
        created.append(post)
    db.add(SiteSetting(key=MARKER, value="true", updated_at=now))
    return created
