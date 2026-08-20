from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JOBPORTAL_TESTING", "true")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("EMAIL_FROM_EMAIL", "alerts@example.test")

from app.database import Base  # noqa: E402
from app.models import EmailSubscriber, Job  # noqa: E402
from app.routers.jobs import list_jobs  # noqa: E402
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
        }
        inspector = inspect(engine)
        for table, names in expected.items():
            actual = {index["name"] for index in inspector.get_indexes(table)}
            assert names <= actual
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
