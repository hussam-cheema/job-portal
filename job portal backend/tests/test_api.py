from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure test DB before app import side effects where possible
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["JWT_SECRET"] = "test-secret-with-at-least-thirty-two-characters"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-password"
os.environ["JOBPORTAL_TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["R2_ENABLED"] = "false"

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app import models  # noqa: E402, F401
from app.auth import ensure_admin_user  # noqa: E402


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    ensure_admin_user(db)
    db.close()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] in {"ok", "degraded"}


def test_readiness(client: TestClient):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "database": "up"}


def test_login_and_create_job(client: TestClient):
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.post(
        "/api/admin/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Python Developer",
            "description": "<p>Build APIs in Pakistan.</p>",
            "published_date": "2026-07-01T00:00:00",
            "job_type": "private",
            "cities": ["Karachi"],
            "skills": ["Python"],
            "tags": ["Software"],
        },
    )
    assert r.status_code == 200
    job_id = r.json()["id"]

    r = client.get(f"/api/jobs/{job_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Python Developer"

    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_contact(client: TestClient):
    r = client.post(
        "/api/contact",
        json={"name": "Ali", "email": "ali@gmail.com", "message": "Hello from a real user."},
    )
    assert r.status_code == 200


def test_contact_validation_limits(client: TestClient):
    r = client.post(
        "/api/contact",
        json={
            "name": "A" * 51,
            "email": "ali@gmail.com",
            "message": "Hello",
        },
    )
    assert r.status_code in {400, 422}

    r = client.post(
        "/api/contact",
        json={
            "name": "Ali",
            "email": "not-an-email",
            "message": "Hello there",
        },
    )
    assert r.status_code in {400, 422}

    r = client.post(
        "/api/contact",
        json={
            "name": "Ali",
            "email": "x@mailinator.com",
            "message": "Spam attempt",
        },
    )
    assert r.status_code == 400

    r = client.post(
        "/api/contact",
        json={
            "name": "Ali'; DROP TABLE users;--",
            "email": "ali@gmail.com",
            "message": "'; or '1'='1",
        },
    )
    assert r.status_code == 400


def test_stats_open_for_apply(client: TestClient):
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    token = r.json()["access_token"]
    from datetime import datetime, timedelta

    future = (datetime.utcnow() + timedelta(days=10)).isoformat()
    past = (datetime.utcnow() - timedelta(days=10)).isoformat()
    client.post(
        "/api/admin/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Open Role",
            "description": "<p>Still open for applications with enough detail here.</p>",
            "published_date": datetime.utcnow().isoformat(),
            "deadline_date": future,
            "job_type": "private",
        },
    )
    client.post(
        "/api/admin/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Closed Role",
            "description": "<p>Deadline already passed for this listing.</p>",
            "published_date": datetime.utcnow().isoformat(),
            "deadline_date": past,
            "job_type": "private",
        },
    )
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert "open_for_apply" in data
    assert data["open_for_apply"] >= 1


def test_embeddings_similarity():
    from app.services.embeddings import text_similarity, answer_matches_question

    assert text_similarity("software engineer backend python", "python backend engineer") > 0.2
    assert answer_matches_question("What is REST?", "REST is an architectural style for APIs using HTTP.")
    assert not answer_matches_question("What is REST?", "See video")


def test_admin_password_change(client: TestClient):
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    token = login.json()["access_token"]
    changed = client.put(
        "/api/admin/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "admin-password", "new_password": "new-admin-password"},
    )
    assert changed.status_code == 200
    assert client.post(
        "/api/auth/login", json={"username": "admin", "password": "new-admin-password"}
    ).status_code == 200


def test_account_locks_after_four_failed_attempts_and_resets_credentials(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import auth_recovery

    delivered: dict[str, str] = {}

    def capture_email(*, reset_url: str, reason: str) -> None:
        delivered["url"] = reset_url
        delivered["reason"] = reason

    monkeypatch.setattr(auth_recovery, "_send_password_reset_email", capture_email)

    for _ in range(3):
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )
        assert response.status_code == 401

    locked = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert locked.status_code == 423
    assert "account locked" in locked.json()["detail"].lower()
    assert "repeated failed" in delivered["reason"]

    assert client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-password"},
    ).status_code == 423

    token = parse_qs(urlparse(delivered["url"]).query)["token"][0]
    reset = client.post(
        "/api/auth/reset-credentials",
        json={
            "token": token,
            "username": "new-admin",
            "new_password": "replacement-password",
        },
    )
    assert reset.status_code == 200
    assert client.post(
        "/api/auth/login",
        json={"username": "new-admin", "password": "replacement-password"},
    ).status_code == 200
    assert client.post(
        "/api/auth/reset-credentials",
        json={
            "token": token,
            "username": "another-admin",
            "new_password": "another-replacement-password",
        },
    ).status_code == 400


def test_forgot_password_email_resets_username_and_revokes_existing_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import auth_recovery

    delivered: dict[str, str] = {}

    def capture_email(*, reset_url: str, reason: str) -> None:
        delivered["url"] = reset_url
        delivered["reason"] = reason

    monkeypatch.setattr(auth_recovery, "_send_password_reset_email", capture_email)

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    old_token = login.json()["access_token"]

    requested = client.post("/api/auth/forgot-password")
    assert requested.status_code == 200
    assert "forgot password" in delivered["reason"]

    token = parse_qs(urlparse(delivered["url"]).query)["token"][0]
    reset = client.post(
        "/api/auth/reset-credentials",
        json={
            "token": token,
            "username": "recovered-admin",
            "new_password": "recovered-password",
        },
    )
    assert reset.status_code == 200
    assert client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}
    ).status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"username": "recovered-admin", "password": "recovered-password"},
    ).status_code == 200


def test_forgot_password_reports_cooldown_without_claiming_new_delivery(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import auth_recovery

    sent = 0

    def capture_email(*, reset_url: str, reason: str) -> None:
        nonlocal sent
        sent += 1

    monkeypatch.setattr(auth_recovery, "_send_password_reset_email", capture_email)

    first = client.post("/api/auth/forgot-password")
    second = client.post("/api/auth/forgot-password")

    assert first.status_code == 200
    assert "has been sent" in first.json()["message"]
    assert second.status_code == 200
    assert "requested recently" in second.json()["message"]
    assert sent == 1


def test_forgot_password_rate_limits_repeated_ip_requests(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import auth_recovery

    monkeypatch.setattr(auth_recovery, "_send_password_reset_email", lambda **_kwargs: None)
    for _ in range(5):
        assert client.post("/api/auth/forgot-password").status_code == 200

    blocked = client.post("/api/auth/forgot-password")
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "3600"


def test_recovery_email_uses_fixed_admin_recipient(monkeypatch: pytest.MonkeyPatch):
    from app.services import auth_recovery

    sent: dict[str, object] = {}

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int):
            sent["connection"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self, *, context):
            sent["starttls"] = context

        def ehlo(self):
            sent["ehlo_count"] = int(sent.get("ehlo_count", 0)) + 1

        def send_message(self, message):
            sent["message"] = message
            return {}

    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "no-reply@example.test")
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_RECOVERY_EMAIL", raising=False)
    monkeypatch.setattr(auth_recovery.smtplib, "SMTP", FakeSMTP)

    auth_recovery._send_password_reset_email(
        reset_url="https://example.test/reset-password?token=secret",
        reason="test",
    )

    message = sent["message"]
    assert message["To"] == "hussam.cheema7102@gmail.com"
    assert "token=secret" in message.get_body(preferencelist=("plain",)).get_content()


def test_gmail_app_password_spaces_are_removed(monkeypatch: pytest.MonkeyPatch):
    from app.services import auth_recovery

    sent: dict[str, object] = {}

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            return None

        def starttls(self, *, context):
            return None

        def login(self, username: str, password: str):
            sent["login"] = (username, password)

        def send_message(self, message):
            return {}

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "admin@example.test")
    monkeypatch.setenv("SMTP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "admin@example.test")
    monkeypatch.setenv("SMTP_AUTH", "true")
    monkeypatch.setattr(auth_recovery.smtplib, "SMTP", FakeSMTP)

    auth_recovery._send_password_reset_email(
        reset_url="https://example.test/reset-password?token=secret",
        reason="test",
    )

    assert sent["login"] == ("admin@example.test", "abcdefghijklmnop")


def test_existing_hashed_admin_does_not_revalidate_bootstrap_password(
    monkeypatch: pytest.MonkeyPatch,
):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
    ensure_admin_user(db)
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    ensure_admin_user(db)
    db.close()


def test_admin_bootstrap_rejects_short_password(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    with pytest.raises(RuntimeError, match="12 to 72"):
        ensure_admin_user(db)
    db.close()


def test_monthly_analytics(client: TestClient):
    headers = {"user-agent": "Mozilla/5.0", "cf-ipcountry": "PK", "cf-region": "Sindh"}
    assert client.post(
        "/api/analytics/visit",
        headers=headers,
        json={"visitor_id": "visitor-one", "path": "/jobs/python-developer"},
    ).status_code == 201
    client.post(
        "/api/analytics/visit",
        headers=headers,
        json={"visitor_id": "visitor-two", "path": "/"},
    )
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    response = client.get(
        "/api/admin/analytics",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["unique_visitors"] == 2
    assert data["page_views"] == 2
    assert data["locations"][0]["country"] == "PK"


def test_realtime_analytics_and_heartbeat_do_not_duplicate_page_views(client: TestClient):
    headers = {"user-agent": "Mozilla/5.0", "cf-ipcountry": "PK"}
    payload = {"visitor_id": "realtime-visitor", "path": "/jobs/live-role"}
    assert client.post("/api/analytics/visit", headers=headers, json=payload).status_code == 201
    assert client.post("/api/analytics/visit", headers=headers, json=payload).status_code == 201

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    live = client.get("/api/admin/analytics/realtime?window_minutes=5", headers=auth)
    assert live.status_code == 200
    assert live.json()["active_visitors"] == 1
    assert live.json()["pages"][0]["path"] == "/jobs/live-role"

    monthly = client.get("/api/admin/analytics", headers=auth)
    assert monthly.json()["page_views"] == 1


def test_analytics_ignores_browser_location_hints(client: TestClient):
    response = client.post(
        "/api/analytics/visit",
        headers={"user-agent": "Mozilla/5.0"},
        json={
            "visitor_id": "visitor-locale-hint",
            "path": "/jobs/test",
            "country_hint": "US",
            "region_hint": "America/New_York",
        },
    )
    assert response.status_code == 201

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    dashboard = client.get(
        "/api/admin/analytics",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    ).json()
    assert dashboard["locations"] == [
        {"country": "Unknown", "region": None, "visitors": 1, "page_views": 1}
    ]


def test_qna_refresh_replaces_only_after_strict_title_match(monkeypatch: pytest.MonkeyPatch):
    from app.models import JobQnA
    from app.services import qna as qna_service

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
    db.add(
        JobQnA(
            id="old-qna",
            job_id="job-1",
            question="Old question?",
            answer="Old answer that should be replaced.",
        )
    )
    db.commit()

    videos = [
        {"video_id": "match", "title": "Python Developer interview", "url": "https://youtu.be/match"},
        {"video_id": "reject", "title": "Java Developer interview", "url": "https://youtu.be/reject"},
    ]
    monkeypatch.setattr(qna_service, "search_youtube", lambda *args, **kwargs: videos)
    monkeypatch.setattr(
        qna_service,
        "rank_by_similarity",
        lambda *args, **kwargs: [
            {**videos[0], "title_similarity": 0.97},
            {**videos[1], "title_similarity": 0.2},
        ],
    )
    monkeypatch.setattr(qna_service, "get_transcript", lambda video_id: "transcript")
    monkeypatch.setattr(qna_service, "get_top_comments", lambda video_id, **_kwargs: [])
    monkeypatch.setattr(
        qna_service,
        "extract_qna_from_video",
        lambda **kwargs: [{"question": "What is Python?", "answer": "Python is a programming language.", "source": "transcript"}],
    )

    result = qna_service.fetch_qna_for_job_title(
        db, job_id="job-1", job_title="Python Developer"
    )
    rows = db.query(JobQnA).filter(JobQnA.job_id == "job-1").all()
    assert result["videos_scanned"] == 1
    assert len(rows) == 1
    assert rows[0].id != "old-qna"
    assert rows[0].youtube_url == "https://youtu.be/match"
    db.close()


def test_qna_no_match_keeps_existing_rows_and_returns_visible_error(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.models import JobQnA
    from app.services import qna as qna_service

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
    db.add(
        JobQnA(
            id="existing-qna",
            job_id="job-no-match",
            question="Existing question?",
            answer="Existing answer remains available.",
        )
    )
    db.commit()
    monkeypatch.setattr(qna_service, "search_youtube", lambda *args, **kwargs: [])

    result = qna_service.fetch_qna_for_job_title(
        db, job_id="job-no-match", job_title="Uncommon Specialist"
    )

    assert result["count"] == 0
    assert "No sufficiently relevant" in result["error"]
    assert [row.id for row in result["items"]] == ["existing-qna"]
    assert db.query(JobQnA).filter(JobQnA.job_id == "job-no-match").count() == 1
    db.close()


def test_sitemap_data_includes_newly_created_job(client: TestClient):
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    created = client.post(
        "/api/admin/jobs",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={
            "title": "Fresh Sitemap Role",
            "description": "A newly published role for sitemap verification.",
            "published_date": "2026-07-14T00:00:00",
            "job_type": "private",
            "cities": ["Karachi"],
        },
    )
    assert created.status_code == 200
    slug = created.json()["slug"]
    sitemap = client.get("/api/sitemap-data")
    assert sitemap.status_code == 200
    assert any(url["loc"].endswith(f"/jobs/{slug}") for url in sitemap.json()["urls"])
