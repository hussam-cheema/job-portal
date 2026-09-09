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
