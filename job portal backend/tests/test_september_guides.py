import os
import re
from datetime import datetime
from pathlib import Path
from struct import unpack

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JOBPORTAL_TESTING", "true")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base
from app.content.september_guides import SEPTEMBER_GUIDES
from app.models import BlogPost, SEOMeta
from app.services.september_guide_seed import publish_september_guides_once


def test_five_complete_sourced_guides_and_images():
    assert len(SEPTEMBER_GUIDES) == 5
    assert len({g['slug'] for g in SEPTEMBER_GUIDES}) == 5
    assert len({g['edition_date'] for g in SEPTEMBER_GUIDES}) == 5
    root = Path(__file__).resolve().parents[2] / 'job portal frontend/public'
    for guide in SEPTEMBER_GUIDES:
        content = guide['content']
        assert len(re.findall(r"\b[\w’'-]+\b", re.sub('<[^>]+>', ' ', content))) >= 2000
        assert len(guide['meta_title']) <= 60
        assert 135 <= len(guide['meta_description']) <= 160
        assert guide['focus_keyword'].lower() in (guide['title'] + content).lower()
        assert '<h1' not in content and '<script' not in content
        assert content.count('<h2') >= 8
        assert '.gov.pk/' in content
        assert 1 <= len(re.findall(r'href="/', content)) <= 8
        src = re.search(r'<img src="([^"]+)"', content).group(1)
        png = (root / src.lstrip('/')).read_bytes()
        assert png[:8] == b'\x89PNG\r\n\x1a\n'
        assert unpack('>II', png[16:24]) == (1200, 630)
        assert 'loading="eager"' in content


def test_publishing_is_atomic_preserves_edits_and_does_not_resurrect():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        before = datetime.utcnow()
        assert len(publish_september_guides_once(db)) == 5
        db.rollback()
        assert db.query(BlogPost).count() == 0
        posts = publish_september_guides_once(db)
        db.commit()
        assert len(posts) == 5
        assert all(p.published_at >= before for p in posts)
        assert db.query(SEOMeta).count() == 5
        posts[0].content = 'User editorial update'
        db.delete(posts[1])
        db.commit()
        assert publish_september_guides_once(db) == []
        db.commit()
        assert db.query(BlogPost).count() == 4
        assert db.get(BlogPost, posts[0].id).content == 'User editorial update'


def test_existing_slug_is_never_overwritten():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        guide = SEPTEMBER_GUIDES[0]
        db.add(BlogPost(id='existing', slug=guide['slug'], title='CMS title', content='CMS body', tags=[]))
        db.commit()
        assert len(publish_september_guides_once(db)) == 4
        db.commit()
        assert db.get(BlogPost, 'existing').content == 'CMS body'


def test_editorial_release_survives_unrelated_startup_failure(monkeypatch):
    import asyncio
    from sqlalchemy.orm import sessionmaker
    from app import database, main

    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, 'SessionLocal', factory)
    monkeypatch.setenv('JOBPORTAL_TESTING', 'false')
    monkeypatch.setenv('SEED_ON_STARTUP', 'false')
    def failed_legacy_init():
        raise RuntimeError('Unrelated legacy migration failure')
    monkeypatch.setattr(main, 'init_db', failed_legacy_init)
    for name in ('sync_taxonomy_pages_v1', 'sync_directory_page_slugs_v2', 'sync_job_directory_pages_v3'):
        monkeypatch.setattr(main, name, lambda db: [])
    for name in ('_warm_embedding_cache_in_background', '_start_newsletter_retry_worker', '_start_market_report_worker', 'flush_production_logs'):
        monkeypatch.setattr(main, name, lambda: None)
    async def run():
        async with main.lifespan(main.app):
            pass
    asyncio.run(run())
    with factory() as db:
        assert db.query(BlogPost).count() == 5
        assert db.query(SEOMeta).count() == 5
