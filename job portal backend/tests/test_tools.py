from __future__ import annotations

import os

os.environ.setdefault("SEED_ON_STARTUP", "false")
os.environ.setdefault("JWT_SECRET", "test-secret-with-at-least-thirty-two-characters")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin-password")
os.environ.setdefault("JOBPORTAL_TESTING", "true")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("R2_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import ensure_admin_user
from app.database import Base, get_db
from app.main import app
from app.seed import ensure_default_tools


@pytest.fixture()
def tools_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

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
    db.commit()
    db.close()
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def _admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin-password"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_default_tool_directory_is_seeded_without_n_plus_one_shape(tools_client: TestClient):
    response = tools_client.get("/api/tools")
    assert response.status_code == 200
    categories = response.json()
    assert [item["title"] for item in categories] == [
        "Tax & Salary Tools",
        "Tools for Students",
        "Image Editing Tools",
        "Document Tools",
    ]
    assert categories[0]["tools"][0]["slug"] == "pakistan-tax-calculator"
    assert categories[0]["tools"][1]["slug"] == "government-salary-calculator"
    assert categories[0]["tools"][1]["tool_kind"] == "government_salary_calculator"
    assert categories[1]["tools"][0]["slug"] == "cgpa-calculator"
    assert [tool["slug"] for tool in categories[1]["tools"]] == [
        "cgpa-calculator",
        "resume-builder",
        "cover-letter",
        "api",
    ]
    assert categories[1]["tools"][1]["tool_kind"] == "resume_builder"
    assert categories[1]["tools"][2]["tool_kind"] == "cover_letter"
    assert categories[1]["tools"][3]["tool_kind"] == "student_api"
    assert categories[2]["tools"] == []
    assert categories[3]["tools"][0]["slug"] == "docx-pdf-converter"
    assert categories[3]["tools"][0]["tool_kind"] == "document_converter"


def test_admin_can_create_category_and_tool_with_unique_branch_colours(tools_client: TestClient):
    headers = _admin_headers(tools_client)
    first = tools_client.post(
        "/api/admin/tool-categories",
        headers=headers,
        json={
            "title": "Career Planning",
            "slug": "career-planning",
            "content": "<p>Plan a career.</p>",
            "icon_key": "sparkles",
            "is_published": True,
        },
    )
    second = tools_client.post(
        "/api/admin/tool-categories",
        headers=headers,
        json={
            "title": "Writing Tools",
            "slug": "writing-tools",
            "content": "",
            "icon_key": "document",
            "is_published": True,
        },
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["color_index"] != second.json()["color_index"]

    tool = tools_client.post(
        "/api/admin/tool-pages",
        headers=headers,
        json={
            "category_id": first.json()["id"],
            "title": "Career Checklist",
            "slug": "career-checklist",
            "content": "<p>A managed tool page.</p>",
            "tool_kind": "content",
            "is_published": True,
            "seo": {"meta_title": "Career Checklist for Pakistan"},
        },
    )
    assert tool.status_code == 200
    public = tools_client.get("/api/tools/career-checklist")
    assert public.status_code == 200
    assert public.json()["content"] == "<p>A managed tool page.</p>"
    seo = tools_client.get(f"/api/seo/tool/{tool.json()['id']}")
    assert seo.status_code == 200
    assert seo.json()["meta_title"] == "Career Checklist for Pakistan"


def test_tool_slugs_are_unique_and_categories_with_tools_are_protected(tools_client: TestClient):
    headers = _admin_headers(tools_client)
    admin = tools_client.get("/api/admin/tools", headers=headers).json()
    tax_category = next(item for item in admin["categories"] if item["slug"] == "tax-salary-tools")
    duplicate = tools_client.post(
        "/api/admin/tool-pages",
        headers=headers,
        json={
            "category_id": tax_category["id"],
            "title": "Duplicate",
            "slug": "pakistan-tax-calculator",
            "tool_kind": "content",
        },
    )
    assert duplicate.status_code == 400
    protected = tools_client.delete(
        f"/api/admin/tool-categories/{tax_category['id']}",
        headers=headers,
    )
    assert protected.status_code == 409
