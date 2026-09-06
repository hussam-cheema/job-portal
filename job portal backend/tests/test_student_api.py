from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from email.message import EmailMessage
from uuid import uuid4

os.environ.setdefault("SEED_ON_STARTUP", "false")
os.environ.setdefault("JWT_SECRET", "test-secret-with-at-least-thirty-two-characters")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin-password")
os.environ.setdefault("JOBPORTAL_TESTING", "true")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("R2_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import ensure_admin_user
from app.database import Base, get_db
from app.main import app
from app.models import (
    BlogPost,
    EmailSubscriber,
    Job,
    JobAttachment,
    StudentApiSecurityEvent,
    SubscriberApiAccess,
)
from app.seed import ensure_default_tools
from app.services import student_api as student_api_service


@pytest.fixture()
def student_api_context(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    sent_messages: list[EmailMessage] = []

    monkeypatch.setenv("EMAIL_FROM_EMAIL", "alerts@example.test")
    monkeypatch.setattr(
        student_api_service,
        "email_delivery_status",
        lambda: ("resend", True, "Resend HTTPS delivery is configured."),
    )
    monkeypatch.setattr(
        student_api_service,
        "deliver_email_message",
        lambda message: sent_messages.append(message),
    )
    student_api_service._burst_hits.clear()

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    db = session_factory()
    ensure_admin_user(db)
    ensure_default_tools(db)
    db.add(
        Job(
            id="job-api-test",
            slug="student-api-test-job",
            title="Student API Test Job",
            description='<p>Complete job description.</p><img src="https://cdn.example.test/ad.jpg">',
            published_date=datetime(2026, 9, 5, 10, 0, 0),
            deadline_date=datetime(2026, 9, 30, 23, 59, 0),
            salary_range="PKR 80,000",
            source="Example Organization",
            newspaper="Daily Example",
            reference_url="https://example.test/reference",
            application_url="https://example.test/apply",
            experience_required="2 years",
            education_required="Bachelor's degree",
            skills=["Python", "SQL"],
            job_type="private",
            cities=["Lahore"],
            provinces=["Punjab"],
            tags=["Technology"],
            keywords="student api test",
        )
    )
    db.add(
        JobAttachment(
            id="attachment-api-test",
            job_id="job-api-test",
            file_type="image/jpeg",
            file_size=3210,
            s3_path="jobs/api-test/ad.jpg",
            original_name="advertisement.jpg",
            is_inline_image=True,
            public_url="https://cdn.example.test/attachment.jpg",
        )
    )
    db.add(
        BlogPost(
            id="blog-api-test",
            slug="student-api-test-blog",
            title="Student API Test Blog",
            excerpt="A complete API test article.",
            content="<h2>Full article</h2><p>Every published word is here.</p>",
            author="Pakistan Jobs Market",
            category="Student Guides",
            tags=["API", "Projects"],
            is_published=True,
            published_at=datetime(2026, 9, 5, 9, 0, 0),
        )
    )
    db.commit()
    db.close()

    with TestClient(app) as client:
        yield client, session_factory, sent_messages

    app.dependency_overrides.clear()
    student_api_service._burst_hits.clear()
    Base.metadata.drop_all(bind=engine)


def _subscribe_and_key(
    client: TestClient,
    sent_messages: list[EmailMessage],
    email: str,
    *,
    ip: str,
) -> str:
    headers = {"X-Forwarded-For": ip}
    subscribed = client.post("/api/subscriptions", json={"email": email})
    assert subscribed.status_code == 200
    requested = client.post(
        "/api/student-api/request-code",
        json={"email": email},
        headers=headers,
    )
    assert requested.status_code == 200
    assert requested.headers["content-type"].startswith("application/json")
    assert requested.json()["status"] == "code_sent"
    plain = sent_messages[-1].get_body(preferencelist=("plain",)).get_content()
    match = re.search(r"\b(\d{6})\b", plain)
    assert match
    verified = client.post(
        "/api/student-api/verify-code",
        json={"email": email, "code": match.group(1)},
        headers=headers,
    )
    assert verified.status_code == 200
    assert verified.headers["content-type"].startswith("application/json")
    key = verified.json()["api_key"]
    assert key.startswith("pjm_live_")
    return key


def test_student_api_tool_is_seeded_in_students_category(student_api_context):
    client, _session_factory, _sent_messages = student_api_context
    response = client.get("/api/tools")
    assert response.status_code == 200
    students = next(item for item in response.json() if item["slug"] == "tools-for-students")
    assert [tool["slug"] for tool in students["tools"]] == [
        "cgpa-calculator",
        "resume-builder",
        "cover-letter",
        "api",
    ]
    assert students["tools"][-1]["tool_kind"] == "student_api"


def test_non_subscriber_cannot_request_a_key_and_oversized_body_is_rejected(student_api_context):
    client, session_factory, _sent_messages = student_api_context
    response = client.post(
        "/api/student-api/request-code",
        json={"email": "not-subscribed@example.com"},
        headers={"X-Forwarded-For": "198.51.100.11"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "subscription_required"
    oversized = client.post(
        "/api/student-api/request-code",
        content=b"x" * 5000,
        headers={"Content-Type": "application/json", "X-Forwarded-For": "198.51.100.12"},
    )
    assert oversized.status_code == 413
    with session_factory() as db:
        assert db.execute(select(func.count()).select_from(StudentApiSecurityEvent)).scalar() == 3


def test_verification_requests_are_rate_limited_by_ip(student_api_context):
    client, _session_factory, _sent_messages = student_api_context
    headers = {"X-Forwarded-For": "198.51.100.13"}
    for index in range(8):
        response = client.post(
            "/api/student-api/request-code",
            json={"email": f"unknown-{index}@example.com"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "subscription_required"
    blocked = client.post(
        "/api/student-api/request-code",
        json={"email": "unknown-blocked@example.com"},
        headers=headers,
    )
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "3600"


def test_subscriber_receives_one_time_code_and_raw_secrets_are_not_stored(student_api_context):
    client, session_factory, sent_messages = student_api_context
    email = "student.one@example.com"
    key = _subscribe_and_key(client, sent_messages, email, ip="198.51.100.21")
    assert len(sent_messages) == 1
    with session_factory() as db:
        access = db.execute(
            select(SubscriberApiAccess).where(SubscriberApiAccess.subscriber_email == email)
        ).scalar_one()
        assert access.verification_code_hash is None
        assert access.api_key_hash
        assert access.api_key_hash != key
        assert key not in repr(access.__dict__)
        assert access.api_key_prefix == key[:18]
        assert access.requests_used == 0


def test_key_retrieves_complete_jobs_and_blogs_and_counts_quota(student_api_context):
    client, _session_factory, sent_messages = student_api_context
    key = _subscribe_and_key(
        client,
        sent_messages,
        "student.data@example.com",
        ip="198.51.100.31",
    )
    headers = {"X-API-Key": key, "X-Forwarded-For": "198.51.100.31"}

    jobs = client.get("/api/student/v1/jobs?page=1&page_size=10", headers=headers)
    assert jobs.status_code == 200
    assert jobs.headers["X-Quota-Used"] == "1"
    job = jobs.json()["items"][0]
    assert "Complete job description" in job["description"]
    assert job["advertisement_images"] == ["https://cdn.example.test/ad.jpg"]
    assert job["attachments"][0]["public_url"] == "https://cdn.example.test/attachment.jpg"
    assert job["education_required"] == "Bachelor's degree"

    blog = client.get("/api/student/v1/blog-posts/student-api-test-blog", headers=headers)
    assert blog.status_code == 200
    assert blog.headers["X-Quota-Used"] == "2"
    assert "Every published word" in blog.json()["item"]["content"]
    assert blog.json()["item"]["tags"] == ["API", "Projects"]

    quota = client.get("/api/student/v1/quota", headers=headers)
    assert quota.status_code == 200
    assert quota.json()["requests_used"] == 2
    assert quota.json()["requests_remaining"] == 48
    assert quota.headers["X-Quota-Used"] == "2"


def test_every_student_api_route_returns_json(student_api_context):
    client, _session_factory, sent_messages = student_api_context
    key = _subscribe_and_key(
        client,
        sent_messages,
        "student.json@example.com",
        ip="198.51.100.32",
    )
    headers = {"X-API-Key": key, "X-Forwarded-For": "198.51.100.32"}

    responses = [
        client.get("/api/student/v1/quota", headers=headers),
        client.get("/api/student/v1/jobs", headers=headers),
        client.get("/api/student/v1/jobs/student-api-test-job", headers=headers),
        client.get("/api/student/v1/blog-posts", headers=headers),
        client.get("/api/student/v1/blog-posts/student-api-test-blog", headers=headers),
        client.get("/api/student/v1/jobs/missing-job", headers=headers),
        client.get("/api/student/v1/quota"),
        client.post("/api/student-api/request-code", json={"email": "not-an-email"}),
    ]
    assert [response.status_code for response in responses] == [
        200,
        200,
        200,
        200,
        200,
        404,
        401,
        400,
    ]
    for response in responses:
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() is not None

    quota = responses[0].json()
    assert quota["quota_total"] == 50
    assert quota["requests_used"] == 0
    assert quota["requests_remaining"] == 50
    for response in responses[1:5]:
        assert set(response.json()["quota"]) == {"limit", "used", "remaining"}


def test_quota_is_atomic_lifetime_limit_and_key_rotation_does_not_reset_it(student_api_context):
    client, session_factory, sent_messages = student_api_context
    email = "student.quota@example.com"
    ip = "198.51.100.41"
    key = _subscribe_and_key(client, sent_messages, email, ip=ip)
    with session_factory() as db:
        access = db.execute(
            select(SubscriberApiAccess).where(SubscriberApiAccess.subscriber_email == email)
        ).scalar_one()
        access.requests_used = 49
        access.last_code_sent_at = datetime.utcnow() - timedelta(seconds=61)
        db.commit()

    headers = {"Authorization": f"Bearer {key}", "X-Forwarded-For": ip}
    final_allowed = client.get("/api/student/v1/jobs/student-api-test-job", headers=headers)
    assert final_allowed.status_code == 200
    assert final_allowed.headers["X-Quota-Remaining"] == "0"
    blocked = client.get("/api/student/v1/blog-posts", headers=headers)
    assert blocked.status_code == 429
    assert "quota exhausted" in blocked.json()["detail"].lower()

    sent_messages.clear()
    requested = client.post(
        "/api/student-api/request-code",
        json={"email": email},
        headers={"X-Forwarded-For": ip},
    )
    assert requested.status_code == 200
    code = re.search(
        r"\b(\d{6})\b",
        sent_messages[-1].get_body(preferencelist=("plain",)).get_content(),
    ).group(1)
    rotated = client.post(
        "/api/student-api/verify-code",
        json={"email": email, "code": code},
        headers={"X-Forwarded-For": ip},
    )
    assert rotated.status_code == 200
    assert rotated.json()["requests_used"] == 50
    assert rotated.json()["requests_remaining"] == 0
    assert rotated.json()["api_key"] != key
    assert client.get("/api/student/v1/quota", headers=headers).status_code == 401


def test_queries_are_parameterized_rate_limited_and_unsubscribe_revokes_access(student_api_context):
    client, session_factory, sent_messages = student_api_context
    email = "student.security@example.com"
    ip = "198.51.100.51"
    key = _subscribe_and_key(client, sent_messages, email, ip=ip)
    headers = {"X-API-Key": key, "X-Forwarded-For": ip}
    injection = client.get(
        "/api/student/v1/jobs",
        params={"q": "%' OR 1=1; DROP TABLE jobs; --"},
        headers=headers,
    )
    assert injection.status_code == 200
    assert injection.json()["items"] == []
    with session_factory() as db:
        assert db.execute(select(func.count()).select_from(Job)).scalar() == 1
        subscriber = db.execute(
            select(EmailSubscriber).where(EmailSubscriber.subscribed_email == email)
        ).scalar_one()
        unsubscribe_token = subscriber.unsubscribe_token
    unsubscribed = client.post(
        "/api/subscriptions/unsubscribe",
        params={"token": unsubscribe_token},
    )
    assert unsubscribed.status_code == 200
    assert client.get("/api/student/v1/quota", headers=headers).status_code == 401
    with session_factory() as db:
        access = db.execute(
            select(SubscriberApiAccess).where(SubscriberApiAccess.subscriber_email == email)
        ).scalar_one()
        assert access.subscriber_is_active is False
        assert access.is_key_active is False


def test_admin_can_monitor_api_access_without_raw_credentials(student_api_context):
    client, _session_factory, sent_messages = student_api_context
    email = f"admin-view-{uuid4().hex[:8]}@example.com"
    key = _subscribe_and_key(client, sent_messages, email, ip="198.51.100.61")
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-password"},
    )
    summary = client.get(
        "/api/admin/subscriptions",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert summary.status_code == 200
    item = next(
        row for row in summary.json()["student_api_access"]
        if row["subscriber_email"] == email
    )
    assert item["key_prefix"] == key[:18]
    assert item["requests_used"] == 0
    assert "api_key" not in item
    assert "verification_code" not in item
