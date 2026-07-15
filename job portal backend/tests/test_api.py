from __future__ import annotations

import json
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
    assert "no-store" in r.headers["cache-control"]

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


def test_embeddings_similarity(monkeypatch: pytest.MonkeyPatch):
    from app.services import embeddings

    def fake_semantic_vectors(texts: list[str], *, query_first: bool = False):
        if query_first:
            rows = [[1.0, 0.0]]
            for text in texts[1:]:
                lowered = text.lower()
                if "sub inspector" in lowered:
                    rows.append([0.99, 0.05])
                elif "fia" in lowered:
                    rows.append([0.9, 0.2])
                else:
                    rows.append([0.1, 0.99])
            return rows
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(embeddings, "_semantic_embeddings", fake_semantic_vectors)

    assert embeddings.text_similarity("software engineer backend python", "python backend engineer") > 0.2
    assert embeddings.answer_matches_question(
        "What is REST?", "REST is an architectural style for APIs using HTTP."
    )
    assert not embeddings.answer_matches_question("What is REST?", "See video")

    ranked = embeddings.rank_by_similarity(
        "FIA Inspector jobs in government",
        [
            {"title": "Interviews for Government Jobs in Pakistan"},
            {"title": "FIA Sub Inspector Interview Experience and Questions"},
            {"title": "FIA written paper result and interview questions"},
        ],
        score_key="score",
    )
    assert ranked[0]["title"].startswith("FIA Sub Inspector")
    assert ranked[0]["score"] >= 0.6
    generic = next(row for row in ranked if row["title"].startswith("Interviews for"))
    assert generic["score"] < 0.35


def test_openai_embedding_failure_uses_embeddinggemma(monkeypatch: pytest.MonkeyPatch):
    from app.services import embeddings

    used = {"embeddinggemma": False}

    def openai_failure(texts: list[str]):
        raise RuntimeError("OpenAI unavailable")

    def local_vectors(texts: list[str], *, query_first: bool = False):
        used["embeddinggemma"] = True
        return [[1.0, 0.0], [0.8, 0.2]]

    monkeypatch.setattr(embeddings, "_openai_embeddings", openai_failure)
    monkeypatch.setattr(embeddings, "_embeddinggemma_embeddings", local_vectors)

    vectors = embeddings._semantic_embeddings(["query", "candidate"], query_first=True)

    assert used["embeddinggemma"] is True
    assert vectors == [[1.0, 0.0], [0.8, 0.2]]


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
        "extract_qna_from_sources",
        lambda **kwargs: [
            {
                "question": "What is Python?",
                "answer": "Python is a programming language.",
                "source": "transcript",
                "video_index": 1,
            }
        ],
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


def test_qna_collects_all_selected_videos_before_combined_extraction(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.models import JobQnA
    from app.services import qna as qna_service

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
    videos = [
        {"video_id": "first", "title": "FIA Inspector interview", "url": "https://youtu.be/first"},
        {"video_id": "second", "title": "FIA Inspector preparation", "url": "https://youtu.be/second"},
    ]
    searched: dict[str, object] = {}

    def search(*args, **kwargs):
        searched.update(kwargs)
        return videos

    monkeypatch.setattr(qna_service, "search_youtube", search)
    monkeypatch.setattr(
        qna_service,
        "rank_by_similarity",
        lambda *args, **kwargs: [{**video, "title_similarity": 0.9} for video in videos],
    )
    monkeypatch.setattr(qna_service, "get_transcript", lambda video_id: "useful transcript")
    monkeypatch.setattr(qna_service, "get_top_comments", lambda video_id, **kwargs: [])

    extracted_titles: list[str] = []

    def extract(**kwargs):
        extracted_titles.extend(source["title"] for source in kwargs["sources"])
        return [
            {
                "question": "What does FIA investigate?",
                "answer": "FIA investigates federal crimes and related offences.",
                "source": "transcript",
                "video_index": 1,
            }
        ]

    monkeypatch.setattr(qna_service, "extract_qna_from_sources", extract)

    result = qna_service.fetch_qna_for_job_title(
        db, job_id="job-first-match", job_title="FIA Inspector jobs in government"
    )

    assert result["count"] == 1
    assert result["videos_scanned"] == 2
    assert result["error"] is None
    assert searched["max_results"] == 50
    assert extracted_titles == [
        "FIA Inspector interview",
        "FIA Inspector preparation",
    ]
    assert db.query(JobQnA).filter(JobQnA.job_id == "job-first-match").count() == 1
    db.close()


def test_qna_keeps_usable_sources_when_one_selected_video_has_no_content(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import qna as qna_service

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
    videos = [
        {"video_id": "slow", "title": "FIA Inspector interview", "url": "https://youtu.be/slow"},
        {"video_id": "useful", "title": "FIA Inspector test guide", "url": "https://youtu.be/useful"},
    ]
    monkeypatch.setattr(qna_service, "search_youtube", lambda *args, **kwargs: videos)
    monkeypatch.setattr(
        qna_service,
        "rank_by_similarity",
        lambda *args, **kwargs: [{**video, "title_similarity": 0.9} for video in videos],
    )
    monkeypatch.setattr(
        qna_service,
        "get_transcript",
        lambda video_id: None if video_id == "slow" else "useful transcript",
    )
    monkeypatch.setattr(qna_service, "get_top_comments", lambda video_id, **kwargs: [])

    def extract(**kwargs):
        assert [source["video_id"] for source in kwargs["sources"]] == ["useful"]
        return [
            {
                "question": "What is the Inspector role?",
                "answer": "The Inspector role includes investigation and enforcement duties.",
                "source": "transcript",
                "video_index": 2,
            }
        ]

    monkeypatch.setattr(qna_service, "extract_qna_from_sources", extract)

    result = qna_service.fetch_qna_for_job_title(
        db, job_id="job-timeout-retry", job_title="FIA Inspector jobs in government"
    )

    assert result["videos_scanned"] == 2
    assert result["count"] == 1
    assert result["error"] is None
    db.close()


def test_qna_safe_json_preserves_nested_fenced_response():
    from app.services.qna import _safe_json

    parsed = _safe_json(
        """```json
        {"qna":[{"question":"What is FIA?","answer":"It is a federal agency.","video_index":1}]}
        ```"""
    )

    assert parsed["qna"][0]["question"] == "What is FIA?"
    assert parsed["qna"][0]["answer"] == "It is a federal agency."


def test_qna_requires_source_evidence_and_keeps_one_question_per_topic(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import qna as qna_service

    captured: dict[str, str] = {}

    def completion(messages, **_kwargs):
        captured["system"] = messages[0]["content"]
        return """{
          "qna": [
            {
              "question": "What is the permitted age range?",
              "answer": "Candidates can apply from age 18 through 30.",
              "answer_evidence": "Applicants must be between 18 and 30 years old.",
              "topic": "age_eligibility",
              "video_index": 1
            },
            {
              "question": "Is an age relaxation available?",
              "answer": "There is a five-year relaxation.",
              "answer_evidence": "A five-year age relaxation applies.",
              "topic": "age_eligibility",
              "video_index": 1
            },
            {
              "question": "Which qualification is required?",
              "answer": "A bachelor's degree is required.",
              "answer_evidence": "The required qualification is a bachelor's degree.",
              "topic": "education_eligibility",
              "video_index": 1
            },
            {
              "question": "What salary is offered?",
              "answer": "The salary is PKR 100,000.",
              "answer_evidence": "The salary is PKR 100,000.",
              "topic": "salary",
              "video_index": 1
            },
            {
              "question": "When is the closing date?",
              "answer": "Does anyone know the closing date?",
              "answer_evidence": "Does anyone know the closing date?",
              "topic": "deadline",
              "video_index": 1
            }
          ]
        }"""

    monkeypatch.setattr(qna_service, "chat_completion", completion)
    rows = qna_service.extract_qna_from_sources(
        job_title="FIA Inspector",
        sources=[
            {
                "video_index": 1,
                "title": "FIA Inspector eligibility",
                "transcript": (
                    "Applicants must be between 18 and 30 years old. "
                    "A five-year age relaxation applies. "
                    "The required qualification is a bachelor's degree. "
                    "Does anyone know the closing date?"
                ),
                "comments": [],
            }
        ],
        max_qna=20,
        max_source_chars_per_video=16000,
    )

    assert "Never answer from memory" in captured["system"]
    assert "FEW-SHOT EXAMPLES" in captured["system"]
    assert "unanswered questions produce no Q&A" in captured["system"]
    assert "Roman Urdu request" in captured["system"]
    assert [row["topic"] for row in rows] == [
        "age_eligibility",
        "education_eligibility",
    ]
    assert rows[0]["answer"] == "Applicants must be between 18 and 30 years old."
    assert rows[1]["answer"] == "The required qualification is a bachelor's degree."
    assert all("100,000" not in row["answer"] for row in rows)
    assert all("closing date?" not in row["answer"].lower() for row in rows)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("What is the salary?", True),
        ("Does anyone know the salary", True),
        ("Please tell me the last date", True),
        ("Sir BA private kiya ho to kya hm eligible hn plz sir bta den", True),
        ("Sir Inspector investigation ki jobs temporary hoti ha ke permanent", True),
        ("Kya age limit 35 years hai", True),
        ("Applicants must be between 18 and 30 years old.", False),
        ("The application must be submitted online.", False),
        ("AD FIA age limit 22 to 35 years hai.", False),
        ("Sir sab say pahlay MCQs test pir Descriptive test hai", False),
    ],
)
def test_qna_detects_question_like_answers(value: str, expected: bool):
    from app.services.qna import _answer_is_question_like

    assert _answer_is_question_like(value) is expected


def test_qna_chunks_all_source_content_and_keeps_grounded_late_result(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import qna as qna_service

    prompts: list[str] = []
    late_evidence = "Applications must be submitted through the official online portal."

    def completion(messages, **_kwargs):
        prompt = messages[-1]["content"]
        prompts.append(prompt)
        if late_evidence not in prompt:
            return '{"qna":[]}'
        return json.dumps(
            {
                "qna": [
                    {
                        "question": "How should candidates apply?",
                        "answer": late_evidence,
                        "answer_evidence": late_evidence,
                        "topic": "application_process",
                        "video_index": 1,
                    }
                ]
            }
        )

    monkeypatch.setattr(qna_service, "chat_completion", completion)
    rows = qna_service.extract_qna_from_sources(
        job_title="FIA Inspector",
        sources=[
            {
                "video_index": 1,
                "title": "FIA Inspector guide",
                "title_similarity": 0.8,
                "transcript": ("Background information. " * 900) + late_evidence,
                "comments": [],
            }
        ],
        max_qna=20,
        # This legacy parameter controls chunk size only; it must not truncate.
        max_source_chars_per_video=4000,
        timeout_seconds=10,
    )

    assert len(prompts) > 1
    assert any(late_evidence in prompt for prompt in prompts)
    assert rows[0]["answer"] == late_evidence


def test_qna_global_chunk_selection_prefers_higher_ranked_video(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import qna as qna_service

    def completion(_messages, **_kwargs):
        return json.dumps(
            {
                "qna": [
                    {
                        "question": "What is the age limit in the first source?",
                        "answer": "Applicants may apply up to 28 years of age.",
                        "answer_evidence": "Applicants may apply up to 28 years of age.",
                        "topic": "age_eligibility",
                        "video_index": 1,
                    },
                    {
                        "question": "What is the official age limit?",
                        "answer": "The official age limit is 30 years.",
                        "answer_evidence": "The official age limit is 30 years.",
                        "topic": "age_eligibility",
                        "video_index": 2,
                    },
                ]
            }
        )

    monkeypatch.setattr(qna_service, "chat_completion", completion)
    rows = qna_service.extract_qna_from_sources(
        job_title="FIA Inspector",
        sources=[
            {
                "video_index": 1,
                "title": "General guide",
                "title_similarity": 0.71,
                "transcript": "Applicants may apply up to 28 years of age.",
                "comments": [],
            },
            {
                "video_index": 2,
                "title": "Official FIA Inspector eligibility",
                "title_similarity": 0.92,
                "transcript": "The official age limit is 30 years.",
                "comments": [],
            },
        ],
        max_qna=20,
        timeout_seconds=10,
    )

    assert len(rows) == 1
    assert rows[0]["video_index"] == 2
    assert rows[0]["answer"] == "The official age limit is 30 years."


def test_deepseek_qna_disables_thinking_and_retries_empty_json(
    monkeypatch: pytest.MonkeyPatch,
):
    import httpx

    from app.services import llm as llm_service

    payloads: list[dict] = []
    responses = [
        {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]},
        {
            "choices": [
                {
                    "message": {"content": '{"qna":[{"question":"Q?","answer":"Answer."}]}'},
                    "finish_reason": "stop",
                }
            ]
        },
    ]

    class FakeResponse:
        def __init__(self, data: dict):
            self.data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self.data

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, _url, **kwargs):
            payloads.append(kwargs["json"].copy())
            return FakeResponse(responses.pop(0))

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setattr(
        llm_service,
        "resolve_task_llm",
        lambda *_args, **_kwargs: {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "api_key": "test-key",
            "base_url": "https://api.deepseek.com/v1",
            "temperature": 0.1,
            "max_tokens": 4096,
            "thinking": False,
            "response_format": "json_object",
            "empty_response_retries": 1,
        },
    )

    content = llm_service.chat_completion(
        [{"role": "user", "content": "Return JSON"}], timeout_seconds=5
    )

    assert content.startswith('{"qna"')
    assert payloads[0]["thinking"] == {"type": "disabled"}
    assert payloads[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in payloads[1]


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
