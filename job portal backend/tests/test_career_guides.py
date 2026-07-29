from __future__ import annotations

import os
import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JOBPORTAL_TESTING", "true")

from app.database import Base  # noqa: E402
from app.content.career_guides import CAREER_GUIDES
from app.models import BlogPost, SEOMeta, SiteSetting
from app.services.career_guide_seed import (
    CAREER_GUIDES_MARKER,
    publish_career_guides_once,
)


def _word_count(html: str) -> int:
    text = re.sub(r"<[^>]+>", " ", html)
    return len(re.findall(r"\b[\w’'-]+\b", text))


def test_career_guide_library_is_complete_and_seo_ready():
    assert len(CAREER_GUIDES) == 10
    assert len({guide["slug"] for guide in CAREER_GUIDES}) == 10
    assert len({guide["title"] for guide in CAREER_GUIDES}) == 10

    for guide in CAREER_GUIDES:
        assert _word_count(guide["content"]) >= 1000
        assert guide["content"].count("<h2>") >= 5
        assert "<h1>" not in guide["content"]
        assert "Official source" in guide["content"] or "Official and industry source" in guide["content"]
        assert 30 <= len(guide["excerpt"]) <= 600
        assert len(guide["meta_title"]) <= 70
        assert 100 <= len(guide["meta_description"]) <= 170
        assert guide["focus_keyword"].lower() in (
            f"{guide['title']} {guide['content']}".lower()
        )
        assert guide["category"]
        assert len(guide["tags"]) >= 4


def test_career_guide_publisher_is_atomic_and_idempotent():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = session_factory()
    try:
        created = publish_career_guides_once(db_session)
        db_session.commit()

        assert len(created) == 10
        assert db_session.query(BlogPost).filter(BlogPost.is_published.is_(True)).count() == 10
        assert db_session.query(SEOMeta).filter(SEOMeta.entity_type == "blog").count() == 10
        assert db_session.get(SiteSetting, CAREER_GUIDES_MARKER) is not None

        assert publish_career_guides_once(db_session) == []
        db_session.commit()
        assert db_session.query(BlogPost).count() == 10
    finally:
        db_session.close()
