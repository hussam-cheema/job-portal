from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JOBPORTAL_TESTING", "true")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("EMAIL_FROM_EMAIL", "alerts@example.test")

from app.database import Base  # noqa: E402
from app.models import EmailSubscriber, Job, Page, SEOMeta  # noqa: E402
from app.routers.jobs import list_jobs  # noqa: E402
from app.seed import sync_directory_page_slugs_v2  # noqa: E402
from app.services import newsletter  # noqa: E402


def _database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    return engine, session_factory()


def _job(*, description: str = "Job description") -> Job:
    now = datetime.utcnow()
    return Job(
        id=str(uuid4()),
        slug=f"job-{uuid4().hex}",
        title="Database optimization test job",
        description=description,
        published_date=now,
        created_at=now,
        updated_at=now,
    )


def test_composite_indexes_are_created_for_hot_query_paths():
    engine, db = _database()
    try:
        expected = {
            "analytics_visits": {
                "ix_analytics_visitor_path_visited",
                "ix_analytics_verified_visitor_visited",
                "ix_analytics_visitor_path_last_seen",
                "ix_analytics_visits_last_seen_at",
            },
            "jobs": {
                "ix_jobs_published_created",
                "ix_jobs_type_published",
                "ix_jobs_source_published",
                "ix_jobs_newspaper_published",
            },
            "job_attachments": {"ix_job_attachments_job_created"},
            "job_qna": {"ix_job_qna_job_created"},
            "subscription_email_deliveries": {
                "ix_deliveries_due",
                "ix_deliveries_job_status",
            },
            "pages": {
                "ix_pages_slug",
                "uq_pages_type_slug",
                "uq_pages_location_slug",
            },
        }
        inspector = inspect(engine)
        for table, names in expected.items():
            actual = {index["name"] for index in inspector.get_indexes(table)}
            assert names <= actual
    finally:
        db.close()
        engine.dispose()


def test_analytics_timestamp_migration_preserves_original_visit_time(monkeypatch):
    from app import database

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    original_visit_time = "2026-08-27 08:15:00"
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE analytics_visits ("
                    "id VARCHAR(36) PRIMARY KEY, visited_at DATETIME NOT NULL)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO analytics_visits (id, visited_at) "
                    "VALUES ('legacy-visit', :visited_at)"
                ),
                {"visited_at": original_visit_time},
            )

        monkeypatch.setattr(database, "engine", engine)
        monkeypatch.setattr(database, "DATABASE_URL", "sqlite://")
        database._ensure_new_columns()

        columns = {column["name"] for column in inspect(engine).get_columns("analytics_visits")}
        assert "last_seen_at" in columns
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT visited_at, last_seen_at FROM analytics_visits "
                    "WHERE id = 'legacy-visit'"
                )
            ).one()
        assert str(row.visited_at) == original_visit_time
        assert str(row.last_seen_at) == original_visit_time
    finally:
        engine.dispose()


def test_directory_slug_migration_removes_legacy_suffix_without_losing_seo():
    engine, db = _database()
    try:
        organization = Page(
            id=str(uuid4()),
            slug="the-nation",
            title="THE NATION Jobs",
            content="<p>Organization content</p>",
            page_type="organization",
            taxonomy_value="THE NATION",
            is_published=True,
        )
        newspaper = Page(
            id=str(uuid4()),
            slug="the-nation-newspaper",
            title="Jobs in The Nation",
            content="<p>Newspaper content</p>",
            page_type="newspaper",
            taxonomy_value="The Nation",
            is_published=True,
        )
        custom_slug = Page(
            id=str(uuid4()),
            slug="analytics-careers",
            title="Data Science Careers",
            content="<p>Custom directory page</p>",
            page_type="category",
            taxonomy_value="Data Science",
            is_published=True,
        )
        db.add_all([organization, newspaper, custom_slug])
        db.flush()
        db.add(
            SEOMeta(
                id=str(uuid4()),
                entity_type="page",
                entity_id=newspaper.id,
                slug=newspaper.slug,
                meta_title="Custom newspaper SEO title",
                meta_description="Custom newspaper SEO description",
            )
        )
        db.commit()

        changed = sync_directory_page_slugs_v2(db)
        db.commit()

        assert [page.id for page in changed] == [newspaper.id]
        assert organization.slug == "the-nation"
        assert newspaper.slug == "the-nation"
        assert custom_slug.slug == "analytics-careers"
        seo = db.query(SEOMeta).filter(SEOMeta.entity_id == newspaper.id).one()
        assert seo.meta_title == "Custom newspaper SEO title"
        assert seo.meta_description == "Custom newspaper SEO description"
        assert seo.canonical_url.endswith("/newspapers/the-nation")
        assert sync_directory_page_slugs_v2(db) == []
    finally:
        db.close()
        engine.dispose()


def test_job_list_uses_two_queries_and_returns_bounded_description_preview():
    engine, db = _database()
    statements: list[str] = []
    try:
        db.add(_job(description="x" * 5000))
        db.commit()

        def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", capture)
        response = list_jobs(
            q=None,
            source_type=None,
            sector=None,
            category=None,
            city=None,
            province=None,
            company=None,
            newspaper=None,
            education=None,
            employment_type=None,
            tag=None,
            job_type=None,
            date=None,
            date_from=None,
            date_to=None,
            page=1,
            page_size=30,
            db=db,
        )

        selects = [
            statement
            for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
        ]
        assert len(selects) == 2
        assert response.total == 1
        assert len(response.items[0].description or "") == 1600
        assert "jobs.updated_at" not in selects[-1]
    finally:
        db.close()
        engine.dispose()


def test_newsletter_delivery_batch_avoids_recipient_scaled_selects(monkeypatch):
    engine, db = _database()
    statements: list[str] = []
    try:
        job = _job()
        db.add(job)
        for index in range(5):
            db.add(
                EmailSubscriber(
                    user_uuid=str(uuid4()),
                    subscribed_email=f"person-{index}@example.test",
                    unsubscribe_token=f"token-{index}",
                    is_active=True,
                    subscribed_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
        db.flush()
        newsletter.queue_new_job_alert(db, job)
        db.commit()

        monkeypatch.setattr(
            newsletter,
            "_deliver_with_retries",
            lambda _message: SimpleNamespace(message_id="accepted"),
        )

        def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", capture)
        result = newsletter.process_pending_job_alerts(db, job_id=job.id)

        selects = [
            statement
            for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
        ]
        assert result["delivered_count"] == 5
        assert len(selects) <= 5
    finally:
        db.close()
        engine.dispose()
