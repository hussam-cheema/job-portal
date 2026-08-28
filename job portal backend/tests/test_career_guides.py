from __future__ import annotations

import os
import re
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JOBPORTAL_TESTING", "true")

from app.database import Base  # noqa: E402
from app.content.career_guide_enrichments import CAREER_GUIDE_ENRICHMENTS
from app.content.career_guides import CAREER_GUIDES
from app.models import BlogPost, SEOMeta, SiteSetting
from app.services.career_guide_seed import (
    CAREER_GUIDES_ENRICHMENT_MARKER,
    CAREER_GUIDES_MARKER,
    enrich_career_guides_once,
    publish_career_guides_once,
)
from app.services.yoast import analyze_yoast


EXCLUDED_MARKET_ANALYSIS_SLUG = "pakistan-job-market-analysis-2019-21"


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


def test_career_guide_enrichments_add_unique_long_form_analysis_and_images():
    guide_slugs = {guide["slug"] for guide in CAREER_GUIDES}
    guides_by_slug = {guide["slug"]: guide for guide in CAREER_GUIDES}
    assert set(CAREER_GUIDE_ENRICHMENTS) == guide_slugs
    assert EXCLUDED_MARKET_ANALYSIS_SLUG not in CAREER_GUIDE_ENRICHMENTS

    image_root = (
        Path(__file__).resolve().parents[2]
        / "job portal frontend"
        / "public"
        / "blog"
    )
    image_sources: set[str] = set()
    internal_links: list[str] = []
    for slug, enrichment in CAREER_GUIDE_ENRICHMENTS.items():
        content = enrichment["content"]
        assert _word_count(content) >= 1000, slug
        assert content.count("<h2>") >= 5, slug
        assert '<figure class="blog-analysis-figure">' in content
        assert '<img src="/blog/' in content
        assert 'alt="' in content
        assert "<figcaption>" in content
        assert "<table>" in content
        assert 'href="/browse"' in content
        article_links = re.findall(r'href="(/[^\"]+)', content)
        assert len(article_links) >= 2
        internal_links.extend(article_links)
        assert len(enrichment["meta_title"]) <= 60
        assert 140 <= len(enrichment["meta_description"]) <= 160
        guide = guides_by_slug[slug]
        seo_analysis = analyze_yoast(
            title=guide["title"],
            content_html=guide["content"] + content,
            meta_title=enrichment["meta_title"],
            meta_description=enrichment["meta_description"],
            focus_keyword=enrichment["focus_keyword"],
            slug=slug,
        )
        assert seo_analysis["seo_score"] >= 80
        assert seo_analysis["readability_score"] >= 80
        image_source = re.search(r'<img src="(/blog/[^\"]+)"', content)
        assert image_source is not None
        image_sources.add(image_source.group(1))
        assert (image_root / image_source.group(1).removeprefix("/blog/")).is_file()

    assert len(image_sources) == len(CAREER_GUIDE_ENRICHMENTS)
    assert any(link.startswith("/tools/") for link in internal_links)
    assert any(link.startswith("/blog/") for link in internal_links)


def test_career_guide_enrichment_sync_is_versioned_and_preserves_excluded_article():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = session_factory()
    excluded_content = "Independent market-analysis content must remain untouched."
    try:
        excluded = BlogPost(
            id="excluded-market-analysis",
            slug=EXCLUDED_MARKET_ANALYSIS_SLUG,
            title="What 5,394 Job Advertisements Reveal About Pakistan’s Job Market",
            excerpt="Independent analysis",
            content=excluded_content,
            author="Editorial team",
            category="Market Analysis",
            tags=["Pakistan jobs"],
            is_published=True,
        )
        db_session.add(excluded)
        publish_career_guides_once(db_session)
        db_session.commit()

        before_counts = {
            post.slug: _word_count(post.content)
            for post in db_session.query(BlogPost).all()
            if post.slug in CAREER_GUIDE_ENRICHMENTS
        }
        updated = enrich_career_guides_once(db_session)
        db_session.commit()

        assert len(updated) == 10
        assert db_session.get(SiteSetting, CAREER_GUIDES_ENRICHMENT_MARKER) is not None
        for post in updated:
            assert _word_count(post.content) >= before_counts[post.slug] + 1000
            assert '<figure class="blog-analysis-figure">' in post.content

        preserved = db_session.query(BlogPost).filter_by(
            slug=EXCLUDED_MARKET_ANALYSIS_SLUG
        ).one()
        assert preserved.content == excluded_content

        assert enrich_career_guides_once(db_session) == []
        db_session.commit()
        assert db_session.query(BlogPost).count() == 11
    finally:
        db_session.close()
