from __future__ import annotations

import json
import os
import base64
import io
import re
import asyncio
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from PIL import Image, ImageChops

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
from app.exceptions import unhandled_exception_handler  # noqa: E402
from app.models import Job  # noqa: E402
from app.services.seo import build_job_structured_data  # noqa: E402
from app.utils import strip_html  # noqa: E402


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
    assert r.headers["x-robots-tag"] == "noindex, nofollow, noarchive"


def test_api_host_robots_allows_crawlers_to_read_noindex_headers(client: TestClient):
    root = client.get("/")
    robots = client.get("/robots.txt")

    assert root.status_code == 200
    assert root.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    assert robots.status_code == 200
    assert robots.text == "User-agent: *\nAllow: /\n"
    assert "Sitemap:" not in robots.text


def test_readiness(client: TestClient):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "database": "up"}


def test_job_structured_data_omits_unknown_optional_fields():
    job = Job(
        id="job-with-intentional-blanks",
        slug="job-with-intentional-blanks",
        title="Job with intentional blanks",
        description="<p>The advertiser supplied only the confirmed facts.</p>",
        published_date=datetime(2026, 8, 11, 12, 0, 0),
        deadline_date=None,
        salary_range="PKR amount not disclosed",
        source="Example employer",
        reference_url=None,
        application_url=None,
        experience_required=None,
        education_required=None,
        skills=[],
        job_type="private",
        cities=[],
        provinces=[],
        tags=[],
        keywords=None,
    )

    structured = build_job_structured_data(job)

    assert structured["@type"] == "JobPosting"
    assert structured["description"].startswith("<p>")
    assert structured["jobLocation"] == [
        {
            "@type": "Place",
            "address": {"@type": "PostalAddress", "addressCountry": "PK"},
        }
    ]
    for optional_field in (
        "validThrough",
        "baseSalary",
        "employmentType",
        "educationRequirements",
        "experienceRequirements",
        "skills",
        "industry",
    ):
        assert optional_field not in structured
    assert "streetAddress" not in structured["jobLocation"][0]["address"]
    assert "postalCode" not in structured["jobLocation"][0]["address"]


def test_job_structured_data_represents_province_and_city_without_fake_address():
    province_job = Job(
        id="province-role",
        slug="province-role",
        title="Province role",
        description="Confirmed role details",
        published_date=datetime(2026, 8, 11, 12, 0, 0),
        source="Example employer",
        cities=[],
        provinces=["Punjab"],
        skills=[None, "SQL", "SQL", ""],
        tags=["Technology"],
    )
    city_job = Job(
        id="city-role",
        slug="city-role",
        title="City role",
        description="Confirmed role details",
        published_date=datetime(2026, 8, 11, 12, 0, 0),
        source="Example employer",
        cities=["Lahore"],
        provinces=["Punjab"],
        skills=[],
        tags=[],
    )

    province_address = build_job_structured_data(province_job)["jobLocation"][0][
        "address"
    ]
    city_address = build_job_structured_data(city_job)["jobLocation"][0]["address"]

    assert province_address == {
        "@type": "PostalAddress",
        "addressRegion": "Punjab",
        "addressCountry": "PK",
    }
    assert city_address == {
        "@type": "PostalAddress",
        "addressLocality": "Lahore",
        "addressRegion": "Punjab",
        "addressCountry": "PK",
    }
    assert build_job_structured_data(province_job)["skills"] == "SQL"


def test_strip_html_decodes_nested_entities():
    assert (
        strip_html("<p>Bachelor&amp;#39;s &amp;amp; future</p>")
        == "Bachelor's & future"
    )


def test_write_freeze_keeps_reads_available_and_rejects_writes(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("WRITE_FREEZE_ENABLED", "true")

    read_response = client.get("/ready")
    write_response = client.post("/api/contact", json={})

    assert read_response.status_code == 200
    assert write_response.status_code == 503
    assert write_response.json()["code"] == "write_freeze"
    assert write_response.headers["retry-after"] == "30"


def test_unhandled_exceptions_return_a_safe_generic_response():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "server": ("testserver", 443),
            "client": ("127.0.0.1", 1234),
            "root_path": "",
            "path": "/api/private-operation",
            "raw_path": b"/api/private-operation",
            "query_string": b"",
            "headers": [],
        }
    )
    response = asyncio.run(
        unhandled_exception_handler(request, RuntimeError("secret database detail"))
    )
    payload = json.loads(response.body)

    assert response.status_code == 500
    assert payload == {
        "detail": "Internal server error",
        "path": "/api/private-operation",
        "fallback": "empty",
    }
    assert "secret database detail" not in response.body.decode("utf-8")
    assert Exception in app.exception_handlers


def test_login_and_create_job(client: TestClient):
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    job_description = (
        "<p>Build APIs in Pakistan.</p>"
        "<table><tbody>"
        "<tr><td><strong>Job ID</strong></td><td><strong>Position</strong></td></tr>"
        "<tr><td>DEV-101</td><td>Python Developer</td></tr>"
        "</tbody></table>"
    )
    r = client.post(
        "/api/admin/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Python Developer",
            "description": job_description,
            "published_date": "2026-07-01T00:00:00",
            "job_type": "private",
            "cities": ["Karachi", "Lahore"],
            "provinces": ["Sindh", "Punjab"],
            "skills": ["Python"],
            "tags": ["Software Engineering"],
        },
    )
    assert r.status_code == 200
    job_id = r.json()["id"]

    r = client.get(f"/api/jobs/{job_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Python Developer"
    assert r.json()["description"] == job_description
    assert r.json()["cities"] == ["Karachi", "Lahore"]
    assert r.json()["provinces"] == ["Sindh", "Punjab"]
    assert "Karachi" in r.json()["location"]
    assert "Punjab" in r.json()["location"]
    assert "no-store" in r.headers["cache-control"]

    r = client.get("/api/jobs?province=Punjab")
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    invalid = client.post(
        "/api/admin/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Invalid Province Role",
            "description": "<p>This job uses a province outside the allowed list.</p>",
            "published_date": "2026-07-01T00:00:00",
            "provinces": ["Not a province"],
        },
    )
    assert invalid.status_code == 400


def test_job_canonical_slug_stays_permanent_and_directory_is_complete(client: TestClient):
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/admin/jobs",
        headers=headers,
        json={
            "title": "Ministry of Defence Jobs 2026",
            "description": "<p>Permanent public opportunity.</p>",
            "published_date": "2026-08-01T00:00:00",
            "deadline_date": "2026-08-31T00:00:00",
            "source": "Ministry of Defence",
            "education_required": "Bachelors",
            "cities": ["Islamabad"],
            "provinces": ["Punjab"],
            "tags": ["Software Engineering"],
        },
    )
    assert created.status_code == 200
    job_id = created.json()["id"]
    original_slug = created.json()["slug"]
    assert original_slug == "ministry-of-defence-jobs-2026"

    updated = client.put(
        f"/api/admin/jobs/{job_id}",
        headers=headers,
        json={"title": "Updated Ministry Careers 2026"},
    )
    assert updated.status_code == 200
    assert updated.json()["slug"] == original_slug

    directory = client.get("/api/site-directory")
    assert directory.status_code == 200
    payload = directory.json()
    assert any(job["slug"] == original_slug for job in payload["jobs"])
    assert any(item["slug"] == "islamabad" for item in payload["taxonomies"]["cities"])
    assert any(item["slug"] == "ministry-of-defence" for item in payload["taxonomies"]["organizations"])
    assert any(item["slug"] == "bachelors" for item in payload["taxonomies"]["qualifications"])

    sitemap = client.get("/api/sitemap-data")
    assert sitemap.status_code == 200
    assert any(
        item["loc"].endswith(f"/jobs/{original_slug}")
        for item in sitemap.json()["urls"]
    )


def test_api_sitemap_redirects_to_the_single_public_sitemap(client: TestClient):
    response = client.get("/sitemap.xml", follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"].endswith("/sitemap.xml")
    assert "/api/" not in response.headers["location"]


def test_admin_pages_self_heal_core_pages(client: TestClient):
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    token = login.json()["access_token"]
    response = client.get(
        "/api/admin/pages", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    pages = {page["slug"]: page for page in response.json()}
    assert {"about", "contact", "privacy", "disclaimer"}.issubset(pages)
    assert "Pakistan Jobs Market" in pages["disclaimer"]["content"]
    assert "Daily Jang" in pages["disclaimer"]["content"]


def test_local_core_pages_receive_production_snapshot_once(monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime
    from app.models import Page
    from app.seed import DEFAULT_PAGES, sync_local_core_pages_once

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        for slug, title, _content in DEFAULT_PAGES:
            session.add(
                Page(
                    id=f"page-{slug}",
                    slug=slug,
                    title=title,
                    content="<p>stale local content</p>",
                    is_published=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
        session.commit()
        monkeypatch.setenv("SITE_URL", "http://localhost:3000")
        assert len(sync_local_core_pages_once(session)) == 4
        session.commit()
        expected = {slug: content for slug, _title, content in DEFAULT_PAGES}
        actual = {row.slug: row.content for row in session.query(Page).all()}
        assert actual == expected
        assert sync_local_core_pages_once(session) == []
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_core_page_and_homepage_seo_defaults_sync_once():
    from datetime import datetime
    from app.models import Page, SEOMeta, SiteSetting
    from app.seed import (
        ABOUT_HTML,
        DEFAULT_PAGE_SEO,
        DISCLAIMER_HTML,
        HOMEPAGE_BRANDING,
        PRIVACY_HTML,
        sync_core_page_content_v2,
        sync_core_page_content_v3,
        sync_homepage_branding_seo_v1,
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        for slug, title in (
            ("about", "About Us"),
            ("privacy", "Privacy Policy"),
            ("disclaimer", "Disclaimer"),
        ):
            session.add(
                Page(
                    id=f"page-{slug}",
                    slug=slug,
                    title=title,
                    content="<p>stale content</p>",
                    is_published=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
        session.add(
            SiteSetting(
                key="site_title",
                value="Old title",
                updated_at=datetime.utcnow(),
            )
        )
        session.commit()

        assert len(sync_core_page_content_v2(session)) == 3
        assert len(sync_core_page_content_v3(session)) == 3
        assert len(sync_homepage_branding_seo_v1(session)) == len(HOMEPAGE_BRANDING)
        session.commit()

        expected_content = {
            "about": ABOUT_HTML,
            "privacy": PRIVACY_HTML,
            "disclaimer": DISCLAIMER_HTML,
        }
        for page in session.query(Page).all():
            assert page.content == expected_content[page.slug]
            if page.slug == "about":
                assert "ATS-standard resume tools" in page.content
            elif page.slug == "privacy":
                assert "ATS-readiness score are processed" in page.content
                assert "does not receive" in page.content
            elif page.slug == "disclaimer":
                assert "does not guarantee parsing" in page.content
            seo = (
                session.query(SEOMeta)
                .filter(
                    SEOMeta.entity_type == "page",
                    SEOMeta.entity_id == page.id,
                )
                .one()
            )
            expected_seo = DEFAULT_PAGE_SEO[page.slug]
            assert seo.focus_keyword == expected_seo["focus_keyword"]
            assert seo.meta_title == expected_seo["meta_title"]
            assert seo.meta_description == expected_seo["meta_description"]
            assert seo.meta_keywords == expected_seo["meta_keywords"]

        for key, value in HOMEPAGE_BRANDING.items():
            assert session.get(SiteSetting, key).value == value

        assert sync_core_page_content_v2(session) == []
        assert sync_core_page_content_v3(session) == []
        assert sync_homepage_branding_seo_v1(session) == []
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_admin_can_update_public_branding_text(client: TestClient):
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    payload = {
        "site_name": "Pakistan Jobs Market",
        "site_title": "Pakistan Jobs Market Careers",
        "site_title_alignment": "right",
        "site_header": "Current jobs across Pakistan",
        "site_description": "A description controlled from the admin dashboard.",
        "footer_copyright": "Copyrights © {year} - Pakistan Jobs Market. All rights reserved.",
        "homepage_focus_keyword": "latest jobs in Pakistan",
        "homepage_meta_title": "Latest Jobs in Pakistan | Pakistan Jobs Market",
        "homepage_meta_description": "Find current government and private jobs across Pakistan.",
        "homepage_meta_keywords": "Pakistan jobs, latest jobs, government jobs",
    }
    updated = client.put("/api/admin/settings/branding", headers=auth, json=payload)

    assert updated.status_code == 200
    assert updated.json()["site_name"] == "Pakistan Jobs Market"
    assert updated.json()["site_title_alignment"] == "right"
    assert updated.json()["logo_url"] == "/pakistan-jobs-market-logo.png"
    public = client.get("/api/settings/branding")
    assert public.status_code == 200
    for key, value in payload.items():
        assert public.json()[key] == value


def test_admin_branding_update_accepts_current_frontend_payload_without_site_name(
    client: TestClient,
):
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    payload = {
        "site_title": "Pakistan Jobs Market",
        "site_title_alignment": "beside_logo",
        "site_header": "Latest government and private jobs in Pakistan",
        "site_description": "Find jobs, career guides, and application tools.",
        "footer_copyright": "Copyright © {year} Pakistan Jobs Market",
        "homepage_focus_keyword": "jobs in Pakistan",
        "homepage_meta_title": "Jobs in Pakistan | Pakistan Jobs Market",
        "homepage_meta_description": "Find current jobs and career guidance in Pakistan.",
        "homepage_meta_keywords": "jobs in Pakistan, career guides",
    }

    response = client.put("/api/admin/settings/branding", headers=auth, json=payload)

    assert response.status_code == 200, response.text
    assert response.json()["site_title_alignment"] == "beside_logo"
    assert response.json()["site_name"]


def test_admin_branding_update_is_partial_and_accepts_long_website_copy(
    client: TestClient,
):
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    description = "Pakistan jobs and career guidance. " * 40

    response = client.put(
        "/api/admin/settings/branding",
        headers=auth,
        json={"site_description": description},
    )

    assert response.status_code == 200, response.text
    assert response.json()["site_description"] == description.strip()
    assert response.json()["site_title"]


def test_watermark_changes_image_and_preserves_format():
    from app.services.watermark import apply_watermark

    source = Image.new("RGB", (900, 300), "white")
    original_buffer = io.BytesIO()
    source.save(original_buffer, format="WEBP")
    watermarked_bytes = apply_watermark(
        original_buffer.getvalue(), "image/webp", strict=True
    )
    watermarked = Image.open(io.BytesIO(watermarked_bytes)).convert("RGB")

    assert Image.open(io.BytesIO(watermarked_bytes)).format == "WEBP"
    difference = ImageChops.difference(source, watermarked)
    visibly_changed = sum(
        1 for pixel in difference.getdata() if max(pixel) >= 16
    )
    assert visibly_changed >= int(source.width * source.height * 0.005)


def test_embedded_description_image_is_watermarked_and_uploaded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from app.services import storage

    captured: dict[str, object] = {}

    def fake_upload(data: bytes, **kwargs):
        captured["data"] = data
        captured.update(kwargs)
        return {
            "s3_path": "job-portal/job/images/watermarked.png",
            "public_url": "https://files.example.test/watermarked.png",
            "file_type": kwargs["content_type"],
            "file_size": len(data),
            "original_name": kwargs["filename"],
            "storage": "r2",
        }

    monkeypatch.setattr(storage, "upload_bytes", fake_upload)
    image = Image.new("RGB", (900, 300), "white")
    image_buffer = io.BytesIO()
    image.save(image_buffer, format="PNG")
    data_url = base64.b64encode(image_buffer.getvalue()).decode("ascii")

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    created = client.post(
        "/api/admin/jobs",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={
            "title": "Watermarked description test",
            "description": f'<p><img src="data:image/png;base64,{data_url}"></p>',
            "published_date": "2026-07-16T00:00:00",
            "job_type": "private",
        },
    )

    assert created.status_code == 200
    assert created.json()["description"] == (
        '<p><img src="https://files.example.test/watermarked.png"></p>'
    )
    assert captured["folder"] == "images"
    assert captured["job_id"] == created.json()["id"]
    uploaded = Image.open(io.BytesIO(captured["data"])).convert("RGB")
    assert ImageChops.difference(image, uploaded).getbbox() is not None


def test_two_legacy_r2_description_images_are_rewatermarked_once(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import storage
    from app.services.watermark import process_description_images

    source = Image.new("RGB", (1000, 700), "white")
    source_buffer = io.BytesIO()
    source.save(source_buffer, format="PNG")
    source_bytes = source_buffer.getvalue()
    uploads: list[dict[str, object]] = []

    def fake_read(url: str, *, max_bytes: int):
        assert max_bytes >= len(source_bytes)
        return {
            "data": source_bytes,
            "content_type": "image/png",
            "metadata": {},
            "filename": Path(urlparse(url).path).name,
            "key": urlparse(url).path.lstrip("/"),
        }

    def fake_upload(data: bytes, **kwargs):
        uploads.append({"data": data, **kwargs})
        index = len(uploads)
        return {
            "s3_path": f"job-portal/job-1/images/watermarked-{index}.png",
            "public_url": f"https://files.example.test/watermarked-{index}.png",
            "file_type": kwargs["content_type"],
            "file_size": len(data),
            "original_name": kwargs["filename"],
            "storage": "r2",
        }

    monkeypatch.setattr(storage, "read_public_object", fake_read)
    monkeypatch.setattr(storage, "upload_bytes", fake_upload)
    description = (
        '<p><img alt="first" src="https://files.example.test/legacy-1.png"></p>'
        '<p><img src="https://files.example.test/legacy-2.png" alt="second"></p>'
    )

    updated = process_description_images(description, "job-1")

    assert updated.count("https://files.example.test/watermarked-") == 2
    assert len(uploads) == 2
    for upload in uploads:
        assert upload["metadata"] == {"watermark-version": "2"}
        rendered = Image.open(io.BytesIO(upload["data"])).convert("RGB")
        assert ImageChops.difference(source, rendered).getbbox() is not None


def test_current_r2_watermark_is_not_applied_twice(monkeypatch: pytest.MonkeyPatch):
    from app.services import storage
    from app.services.watermark import process_description_images

    monkeypatch.setattr(
        storage,
        "read_public_object",
        lambda _url, *, max_bytes: {
            "data": b"unused",
            "content_type": "image/png",
            "metadata": {"watermark-version": "2"},
            "filename": "current.png",
            "key": "job-portal/job-1/images/current.png",
        },
    )
    upload = MagicMock()
    monkeypatch.setattr(storage, "upload_bytes", upload)
    description = '<p><img src="https://files.example.test/current.png"></p>'

    assert process_description_images(description, "job-1") == description
    upload.assert_not_called()


def test_legacy_watermark_migration_updates_jobs_once(monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime

    from app.models import Job, SiteSetting
    from app.services import watermark

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(
        Job(
            id="legacy-watermark-job",
            slug="legacy-watermark-job",
            title="Legacy watermark job",
            description='<p><img src="https://files.example.test/legacy.png"></p>',
            published_date=datetime.utcnow(),
        )
    )
    session.commit()

    process = MagicMock(
        return_value='<p><img src="https://files.example.test/watermarked.png"></p>'
    )
    monkeypatch.setattr(watermark, "process_description_images", process)
    try:
        assert watermark.migrate_legacy_job_watermarks(session) == 1
        session.commit()
        assert session.get(Job, "legacy-watermark-job").description.endswith(
            'watermarked.png"></p>'
        )
        assert session.get(SiteSetting, "job_description_watermarks_v2").value == "1"

        assert watermark.migrate_legacy_job_watermarks(session) == 0
        process.assert_called_once()
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_admin_upload_watermarks_each_of_two_images(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.routers import uploads as uploads_router

    stored: list[dict[str, object]] = []

    def fake_upload(data: bytes, **kwargs):
        stored.append({"data": data, **kwargs})
        index = len(stored)
        return {
            "s3_path": f"job-portal/pending/images/{index}.png",
            "public_url": f"https://files.example.test/{index}.png",
            "file_type": kwargs["content_type"],
            "file_size": len(data),
            "original_name": kwargs["filename"],
            "storage": "r2",
        }

    monkeypatch.setattr(uploads_router, "upload_bytes", fake_upload)
    source_images: list[Image.Image] = []
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    for color, filename in (("white", "first.png"), ("black", "second.png")):
        image = Image.new("RGB", (1000, 700), color)
        source_images.append(image.copy())
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        response = client.post(
            "/api/admin/upload",
            headers=auth,
            files={"file": (filename, buffer.getvalue(), "image/png")},
        )
        assert response.status_code == 200

    assert len(stored) == 2
    for source, upload in zip(source_images, stored, strict=True):
        assert upload["metadata"] == {"watermark-version": "2"}
        rendered = Image.open(io.BytesIO(upload["data"])).convert("RGB")
        assert rendered.size == (1000, 700)
        assert ImageChops.difference(source, rendered).getbbox() is not None


def test_admin_upload_normalizes_extensionless_clipboard_image(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.routers import uploads as uploads_router

    captured: dict[str, object] = {}

    def fake_upload(data: bytes, **kwargs):
        captured.update(kwargs)
        return {
            "s3_path": "job-portal/pending/images/clipboard.png",
            "public_url": "https://files.example.test/clipboard.png",
            "file_type": kwargs["content_type"],
            "file_size": len(data),
            "original_name": kwargs["filename"],
            "storage": "r2",
        }

    monkeypatch.setattr(uploads_router, "upload_bytes", fake_upload)
    image = Image.new("RGB", (40, 30), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    response = client.post(
        "/api/admin/upload",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        files={"file": ("clipboard", buffer.getvalue(), "image/png")},
    )

    assert response.status_code == 200
    assert captured["filename"] == "clipboard.png"
    assert captured["content_type"] == "image/png"
    assert response.json()["public_url"].endswith("/clipboard.png")


def test_admin_can_delete_unattached_editor_upload(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.routers import uploads as uploads_router

    deleted: list[str] = []
    monkeypatch.setattr(
        uploads_router, "delete_object", lambda object_key: deleted.append(object_key)
    )
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    object_key = "job-portal/pending/smoke/images/example.png"

    response = client.delete(
        "/api/admin/upload",
        headers=auth,
        params={"object_key": object_key},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "object_key": object_key}
    assert deleted == [object_key]


def test_job_delete_removes_its_r2_attachments(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.routers import jobs as jobs_router
    from app.routers import uploads as uploads_router

    deleted: list[list[str]] = []
    monkeypatch.setattr(
        jobs_router, "delete_objects", lambda keys: deleted.append(list(keys))
    )
    monkeypatch.setattr(
        uploads_router,
        "upload_bytes",
        lambda data, **kwargs: {
            "s3_path": "job-portal/job-delete/attachments/notice.pdf",
            "public_url": "https://files.example.test/notice.pdf",
            "file_type": kwargs["content_type"],
            "file_size": len(data),
            "original_name": kwargs["filename"],
            "storage": "r2",
        },
    )
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created = client.post(
        "/api/admin/jobs",
        headers=auth,
        json={
            "title": "Temporary R2 cleanup role",
            "description": "<p>Temporary test role.</p>",
            "published_date": "2026-08-02T00:00:00",
            "job_type": "private",
        },
    )
    assert created.status_code == 200
    job_id = created.json()["id"]
    upload = client.post(
        "/api/admin/upload",
        headers=auth,
        data={"job_id": job_id, "as_attachment": "true"},
        files={"file": ("notice.pdf", b"%PDF-smoke", "application/pdf")},
    )
    assert upload.status_code == 200

    response = client.delete(f"/api/admin/jobs/{job_id}", headers=auth)

    assert response.status_code == 200
    assert deleted == [["job-portal/job-delete/attachments/notice.pdf"]]


def test_job_rejects_temporary_clipboard_image_url(client: TestClient):
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    response = client.post(
        "/api/admin/jobs",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={
            "title": "Temporary clipboard image",
            "description": (
                '<p>Image upload is still pending.</p>'
                '<img src="blob:https://example.test/temporary-image">'
            ),
            "published_date": "2026-07-22T00:00:00",
            "job_type": "private",
        },
    )

    assert response.status_code == 400
    assert "still local to the browser" in response.json()["detail"]


def test_public_r2_image_proxy_returns_cached_image(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from app.routers import uploads as uploads_router

    image = Image.new("RGB", (2, 2), "blue")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    expected = buffer.getvalue()
    loaded: dict[str, object] = {}

    def fake_read(object_key: str, *, max_bytes: int):
        loaded["object_key"] = object_key
        loaded["max_bytes"] = max_bytes
        return {
            "data": expected,
            "content_type": "image/png",
            "key": object_key,
        }

    monkeypatch.setattr(uploads_router, "read_public_image_key", fake_read)
    response = client.get(
        "/api/media/r2/job-portal/job-1/images/inline-image.png"
    )

    assert response.status_code == 200
    assert response.content == expected
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert loaded["object_key"] == "job-portal/job-1/images/inline-image.png"
    assert int(loaded["max_bytes"]) > len(expected)


def test_public_r2_image_reader_rejects_non_image_keys_before_contacting_r2(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import storage

    r2_client = MagicMock()
    monkeypatch.setattr(storage, "_r2_client", lambda: r2_client)

    with pytest.raises(ValueError, match="Invalid public image key"):
        storage.read_public_image_key(
            "job-portal/job-1/attachments/private-document.pdf",
            max_bytes=1024,
        )

    r2_client.get_object.assert_not_called()


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


def test_nationwide_and_closed_listing_flags(client: TestClient):
    from app.constants import PAKISTAN_CITIES
    from datetime import datetime, timedelta

    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin-password"})
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created = client.post(
        "/api/admin/jobs",
        headers=auth,
        json={
            "title": "Nationwide Closed Role",
            "description": "<p>A nationwide job with a passed application deadline.</p>",
            "published_date": datetime.utcnow().isoformat(),
            "deadline_date": (datetime.utcnow() - timedelta(days=1)).isoformat(),
            "job_type": "government",
            "cities": PAKISTAN_CITIES,
            "tags": [],
        },
    )
    assert created.status_code == 200
    item = client.get(f"/api/jobs/{created.json()['id']}").json()
    assert item["nationwide"] is True
    assert item["location"] == "Pakistan"
    assert item["applications_closed"] is True


def test_taxonomy_controls_job_categories(client: TestClient):
    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin-password"})
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created_term = client.post(
        "/api/admin/taxonomy",
        headers=auth,
        json={"name": "Data Science", "slug": "data-science"},
    )
    assert created_term.status_code == 200
    public = client.get("/api/taxonomy")
    assert any(term["slug"] == "data-science" for term in public.json())

    valid = client.post(
        "/api/admin/jobs",
        headers=auth,
        json={
            "title": "Data Scientist",
            "description": "<p>Analyze data and build production models.</p>",
            "published_date": "2026-07-16T00:00:00",
            "tags": ["data-science"],
            "skills": ["Python"],
            "cities": ["Lahore"],
        },
    )
    assert valid.status_code == 200
    assert valid.json()["tags"] == ["Data Science"]

    invalid = client.post(
        "/api/admin/jobs",
        headers=auth,
        json={
            "title": "Uncontrolled Category Role",
            "description": "<p>This category was never defined by the administrator.</p>",
            "published_date": "2026-07-16T00:00:00",
            "tags": ["Made Up Category"],
        },
    )
    assert invalid.status_code == 400
    assert "predefined" in invalid.json()["detail"].lower()

    filters = client.get("/api/filters").json()
    assert "Data Science" in filters["tags"]
    assert "Python" not in filters["tags"]
    assert "Lahore" not in filters["tags"]
    assert "Government" not in filters["tags"]
    assert "Private" not in filters["tags"]

    renamed = client.put(
        f"/api/admin/taxonomy/{created_term.json()['id']}",
        headers=auth,
        json={"name": "Analytics", "slug": "analytics"},
    )
    assert renamed.status_code == 200
    changed_job = client.get(f"/api/jobs/{valid.json()['id']}").json()
    assert changed_job["tags"] == ["Analytics"]

    removable = client.post(
        "/api/admin/taxonomy",
        headers=auth,
        json={"name": "Temporary Category", "slug": "temporary-category"},
    )
    assert removable.status_code == 200
    assert client.delete(
        f"/api/admin/taxonomy/{removable.json()['id']}", headers=auth
    ).status_code == 200
    assert all(
        term["slug"] != "temporary-category" for term in client.get("/api/taxonomy").json()
    )
    legal = next(term for term in client.get("/api/admin/taxonomy", headers=auth).json() if term["slug"] == "legal")
    assert client.delete(f"/api/admin/taxonomy/{legal['id']}", headers=auth).status_code == 200
    assert all(term["slug"] != "legal" for term in client.get("/api/taxonomy").json())


def test_subscription_validation_template_and_new_job_alert(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import newsletter

    assert client.post("/api/subscriptions", json={"email": "bad"}).status_code == 400
    assert client.post("/api/subscriptions", json={"email": "x@mailinator.com"}).status_code == 400
    subscriber_emails = [
        "reader@gmail.com",
        "second.reader@gmail.com",
        "third.reader@gmail.com",
    ]
    for email in subscriber_emails:
        subscribed = client.post("/api/subscriptions", json={"email": email})
        assert subscribed.status_code == 200
        assert subscribed.json()["status"] == "subscribed"
    duplicate = client.post("/api/subscriptions", json={"email": "READER@GMAIL.COM"})
    assert duplicate.json()["status"] == "already_subscribed"

    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin-password"})
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    summary = client.get("/api/admin/subscriptions", headers=auth)
    assert summary.status_code == 200
    assert summary.json()["active_subscriber_count"] == len(subscriber_emails)

    updated = client.put(
        "/api/admin/subscriptions/template",
        headers=auth,
        json={
            "subject_template": "New: {job_title} — {site_title}",
            "body_template": "Dear Sir/Madam,\n\nA new job was published on {published_date}:",
        },
    )
    assert updated.status_code == 200

    delivered = []
    monkeypatch.setenv("SMTP_FROM_EMAIL", "hussam.cheema7102@gmail.com")
    monkeypatch.setenv("PUBLIC_API_URL", "https://api.pakistanjobsmarket.com")
    monkeypatch.setattr(newsletter, "_send_smtp_message", lambda message: delivered.append(message))
    job = client.post(
        "/api/admin/jobs",
        headers=auth,
        json={
            "title": "Immediate Alert Role",
            "description": "<p>A new job that must trigger an alert immediately.</p>",
            "published_date": "2026-07-18T08:00:00",
            "deadline_date": "2026-07-25T08:00:00",
            "tags": ["Software Engineering"],
        },
    )
    assert job.status_code == 200
    assert len(delivered) == len(subscriber_emails)
    assert {message["To"] for message in delivered} == set(subscriber_emails)
    plain = delivered[0].get_body(preferencelist=("plain",)).get_content()
    assert "Dear Sir/Madam" in plain
    assert "Immediate Alert Role" in plain
    assert "Deadline:" in plain
    assert "/jobs/" in plain
    assert "unsubscribe" in plain.lower()
    assert "Immediate Alert Role" in delivered[0]["Subject"]
    assert delivered[0]["List-Unsubscribe"].startswith("<")
    assert (
        delivered[0]["List-Unsubscribe-Post"]
        == "List-Unsubscribe=One-Click"
    )
    assert delivered[0]["List-Unsubscribe"].startswith(
        "<https://api.pakistanjobsmarket.com/api/subscriptions/unsubscribe?token="
    )
    assert "job-alerts." in delivered[0]["List-ID"]
    assert delivered[0]["Auto-Submitted"] == "auto-generated"
    assert delivered[0]["X-Entity-Ref-ID"] == job.json()["id"]

    # Editing an existing post must not produce another new-job notification.
    updated_job = client.put(
        f"/api/admin/jobs/{job.json()['id']}",
        headers=auth,
        json={"salary_range": "100000-120000"},
    )
    assert updated_job.status_code == 200
    assert len(delivered) == len(subscriber_emails)

    summary_after_delivery = client.get("/api/admin/subscriptions", headers=auth).json()
    assert summary_after_delivery["last_digest_status"] == "completed"
    assert summary_after_delivery["last_digest_at"] is not None

    unsubscribe_match = re.search(r"/unsubscribe\?token=([^\s]+)", plain)
    assert unsubscribe_match is not None
    unsubscribe_token = unsubscribe_match.group(1)

    removed = client.post(f"/api/subscriptions/unsubscribe?token={unsubscribe_token}")
    assert removed.status_code == 200
    assert removed.json()["status"] == "unsubscribed"
    summary_after_removal = client.get("/api/admin/subscriptions", headers=auth).json()
    assert summary_after_removal["subscriber_count"] == len(subscriber_emails) - 1
    assert summary_after_removal["active_subscriber_count"] == len(subscriber_emails) - 1
    repeated_removal = client.post(f"/api/subscriptions/unsubscribe?token={unsubscribe_token}")
    assert repeated_removal.json()["status"] == "not_subscribed"


def test_job_publish_rolls_back_if_subscriber_outbox_cannot_be_staged(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.routers import jobs as jobs_router

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def fail_outbox(_db, _job):
        raise RuntimeError("simulated outbox write failure")

    monkeypatch.setattr(jobs_router, "queue_new_job_alert", fail_outbox)
    title = "Must Not Publish Without Subscriber Outbox"
    created = client.post(
        "/api/admin/jobs",
        headers=auth,
        json={
            "title": title,
            "description": "<p>This publication must be atomic.</p>",
            "published_date": "2026-07-18T08:30:00",
        },
    )
    assert created.status_code == 500
    listed = client.get("/api/jobs", params={"q": title})
    assert listed.status_code == 200
    assert listed.json()["items"] == []


def test_job_creation_survives_email_delivery_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import newsletter

    assert client.post(
        "/api/subscriptions", json={"email": "delivery-failure@gmail.com"}
    ).status_code == 200
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    monkeypatch.setenv("SMTP_FROM_EMAIL", "hussam.cheema7102@gmail.com")
    monkeypatch.setenv("SMTP_SEND_ATTEMPTS", "1")

    def fail_delivery(_message):
        raise RuntimeError("simulated SMTP outage")

    monkeypatch.setattr(newsletter, "_send_smtp_message", fail_delivery)
    created = client.post(
        "/api/admin/jobs",
        headers=auth,
        json={
            "title": "Job Persists During SMTP Outage",
            "description": "<p>This post must survive failed email delivery.</p>",
            "published_date": "2026-07-18T09:00:00",
        },
    )
    assert created.status_code == 200
    assert client.get(f"/api/jobs/{created.json()['id']}").status_code == 200
    summary = client.get("/api/admin/subscriptions", headers=auth).json()
    assert summary["last_digest_status"] == "retrying"
    assert summary["last_digest_recipients_count"] == 1
    assert summary["last_digest_sent_count"] == 0
    assert summary["last_digest_failed_count"] == 1

    # Failed recipients are durable and the automatic worker can retry only
    # those recipients without sending duplicates to successful subscribers.
    from datetime import datetime
    from sqlalchemy import update
    from app.models import SubscriptionEmailDelivery

    delivered = []
    monkeypatch.setattr(
        newsletter, "_send_smtp_message", lambda message: delivered.append(message)
    )
    override = app.dependency_overrides[get_db]()
    db = next(override)
    try:
        db.execute(
            update(SubscriptionEmailDelivery).values(next_attempt_at=datetime.utcnow())
        )
        db.commit()
        result = newsletter.process_pending_job_alerts(db)
        assert result["delivered_count"] == 1
    finally:
        db.close()
    assert len(delivered) == 1
    retried_summary = client.get("/api/admin/subscriptions", headers=auth).json()
    assert retried_summary["last_digest_status"] == "completed"
    assert retried_summary["last_digest_sent_count"] == 1
    assert retried_summary["last_digest_failed_count"] == 0


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


def test_title_similarity_calibration_keeps_obvious_nadra_match(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import embeddings

    def sixty_percent_cosines(texts: list[str], *, query_first: bool = False):
        assert query_first is True
        return [[1.0, 0.0], *[[0.6, 0.8] for _ in texts[1:]]]

    monkeypatch.setattr(embeddings, "_semantic_embeddings", sixty_percent_cosines)
    ranked = embeddings.rank_by_similarity(
        "NADRA Jobs 2026 – Deputy Assistant Director (Technical) | Apply Online",
        [
            {"title": "NADRA Jobs 2026 | Apply Online | Latest NADRA Careers Pakistan 2026"},
            {"title": "Unrelated cooking tutorial"},
        ],
        score_key="score",
        preserve_order=True,
    )

    assert ranked[0]["score"] == 0.8
    assert ranked[1]["score"] == 0.6


def test_openai_embedding_failure_uses_qwen3(monkeypatch: pytest.MonkeyPatch):
    from app.services import embeddings

    used = {"qwen3": False}

    def openai_failure(texts: list[str]):
        raise RuntimeError("OpenAI unavailable")

    def local_vectors(texts: list[str], *, query_first: bool = False):
        used["qwen3"] = True
        return [[1.0, 0.0], [0.8, 0.2]]

    monkeypatch.setattr(embeddings, "_openai_embeddings", openai_failure)
    monkeypatch.setattr(embeddings, "_qwen3_embeddings", local_vectors)

    vectors = embeddings._semantic_embeddings(["query", "candidate"], query_first=True)

    assert used["qwen3"] is True
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
    headers = {
        "user-agent": "Mozilla/5.0",
        "cf-ipcountry": "PK",
        "cf-region": "Sindh",
        "cf-ipcity": "Karachi",
    }
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
    assert data["locations"][0]["country"] == "Pakistan"
    assert data["locations"][0]["region"] == "Sindh"
    assert data["locations"][0]["city"] == "Karachi"


def test_realtime_analytics_and_heartbeat_do_not_duplicate_page_views(client: TestClient):
    headers = {
        "user-agent": "Mozilla/5.0",
        "cf-ipcountry": "PK",
        "cf-region": "Punjab",
        "cf-ipcity": "Lahore",
    }
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
    assert live.json()["locations"] == [
        {
            "country": "Pakistan",
            "region": "Punjab",
            "city": "Lahore",
            "visitors": 1,
            "last_seen": live.json()["locations"][0]["last_seen"],
        }
    ]

    monthly = client.get("/api/admin/analytics", headers=auth)
    assert monthly.json()["page_views"] == 1


def test_analytics_uses_full_country_names_and_merges_legacy_code_rows(
    client: TestClient,
):
    from datetime import datetime, timedelta

    from app.models import AnalyticsVisit
    from app.routers import analytics as analytics_router

    assert analytics_router._clean_country("US") == "United States"
    assert analytics_router._clean_country("SE") == "Sweden"
    assert analytics_router._clean_country("IE") == "Ireland"

    override = app.dependency_overrides[get_db]()
    db = next(override)
    try:
        now = datetime.utcnow()
        db.add_all(
            [
                AnalyticsVisit(
                    id="legacy-pk-location",
                    visitor_hash="legacy-pk-visitor",
                    path="/legacy-code",
                    country="PK",
                    region="Punjab",
                    city="Lahore",
                    location_verified=True,
                    visited_at=now,
                ),
                AnalyticsVisit(
                    id="full-pakistan-location",
                    visitor_hash="full-pakistan-visitor",
                    path="/full-name",
                    country="Pakistan",
                    region="punjab",
                    city="lahore",
                    location_verified=True,
                    visited_at=now - timedelta(seconds=1),
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    realtime = client.get("/api/admin/analytics/realtime?window_minutes=5", headers=auth)
    monthly = client.get("/api/admin/analytics", headers=auth)

    assert realtime.status_code == 200
    assert realtime.json()["locations"] == [
        {
            "country": "Pakistan",
            "region": "Punjab",
            "city": "Lahore",
            "visitors": 2,
            "last_seen": realtime.json()["locations"][0]["last_seen"],
        }
    ]
    assert monthly.status_code == 200
    assert monthly.json()["locations"] == [
        {
            "country": "Pakistan",
            "region": "Punjab",
            "city": "Lahore",
            "visitors": 2,
            "page_views": 2,
        }
    ]


def test_analytics_resolves_railway_x_real_ip(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.routers import analytics as analytics_router

    looked_up: list[str] = []

    def lookup(ip: str):
        looked_up.append(ip)
        return "Pakistan", "Punjab", "Lahore"

    monkeypatch.setattr(analytics_router, "_lookup_public_ip", lookup)
    response = client.post(
        "/api/analytics/visit",
        headers={"user-agent": "Mozilla/5.0", "x-real-ip": "8.8.8.8"},
        json={"visitor_id": "railway-real-ip-visitor", "path": "/jobs/railway-role"},
    )
    assert response.status_code == 201
    assert looked_up == ["8.8.8.8"]

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    dashboard = client.get(
        "/api/admin/analytics",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    ).json()
    assert dashboard["locations"] == [
        {
            "country": "Pakistan",
            "region": "Punjab",
            "city": "Lahore",
            "visitors": 1,
            "page_views": 1,
        }
    ]


def test_analytics_reuses_verified_location_for_legacy_unknown_rows(client: TestClient):
    visitor = "legacy-unknown-visitor"
    assert client.post(
        "/api/analytics/visit",
        headers={"user-agent": "Mozilla/5.0"},
        json={"visitor_id": visitor, "path": "/first"},
    ).status_code == 201
    assert client.post(
        "/api/analytics/visit",
        headers={
            "user-agent": "Mozilla/5.0",
            "cf-ipcountry": "PK",
            "cf-region": "Sindh",
            "cf-ipcity": "Karachi",
        },
        json={"visitor_id": visitor, "path": "/second"},
    ).status_code == 201

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    dashboard = client.get(
        "/api/admin/analytics",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    ).json()
    assert dashboard["locations"] == [
        {
            "country": "Pakistan",
            "region": "Sindh",
            "city": "Karachi",
            "visitors": 1,
            "page_views": 2,
        }
    ]


def test_analytics_geolocation_uses_country_fallback_and_does_not_cache_failures(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.routers import analytics as analytics_router

    analytics_router._clear_location_cache()
    calls: list[str] = []
    outcomes = [
        {"success": False},
        {"country": "PK"},
    ]

    class Response:
        def __init__(self, payload: dict):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def cfg(*keys, default=None):
        values = {
            "geolocation_enabled": True,
            "geolocation_url": "https://primary.test/{ip}",
            "geolocation_fallback_url": "https://fallback.test/{ip}",
            "geolocation_timeout_seconds": 1,
            "geolocation_cache_seconds": 60,
        }
        return values.get(keys[-1], default)

    def get(url: str, **_kwargs):
        calls.append(url)
        return Response(outcomes.pop(0))

    monkeypatch.setattr(analytics_router, "cfg", cfg)
    monkeypatch.setattr(analytics_router.httpx, "get", get)
    assert analytics_router._lookup_public_ip("8.8.4.4") == ("Pakistan", None, None)
    assert calls == [
        "https://primary.test/8.8.4.4",
        "https://fallback.test/8.8.4.4",
    ]

    # A successful lookup is cached, while the implementation deliberately
    # leaves total failures uncached for a later heartbeat retry.
    assert analytics_router._lookup_public_ip("8.8.4.4") == ("Pakistan", None, None)
    assert len(calls) == 2
    analytics_router._clear_location_cache()
    outcomes.extend(
        [
            {"success": False},
            {"success": False},
            {"success": False},
            {"success": False},
        ]
    )
    assert analytics_router._lookup_public_ip("1.1.1.1") == (None, None, None)
    assert analytics_router._lookup_public_ip("1.1.1.1") == (None, None, None)
    assert len(calls) == 6


def test_infrastructure_analytics_requires_admin_and_reports_capacity(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    assert client.get("/api/admin/infrastructure").status_code == 401
    monkeypatch.setenv("AZURE_COST_MANAGEMENT_ENABLED", "false")
    monkeypatch.setenv("RAILWAY_PLAN", "Hobby")
    monkeypatch.setenv("RAILWAY_MONTHLY_COST_USD", "5")
    monkeypatch.setenv("NEON_PLAN", "Free")
    monkeypatch.setenv("NEON_MONTHLY_COST_USD", "0")
    monkeypatch.setenv("FRONTEND_MONTHLY_COST_USD", "0")
    monkeypatch.setenv("INFRA_CURRENT_STACK_STARTED_MONTH", "2026-08")
    monkeypatch.setenv("INFRA_CURRENT_MONTH_PAID_USD", "2")

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    response = client.get(
        "/api/admin/infrastructure?refresh=true",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert {item["id"] for item in data["storage"]} == {"r2", "database"}
    assert {item["id"] for item in data["compute"]} == {"backend"}
    assert next(item for item in data["storage"] if item["id"] == "database")[
        "used_bytes"
    ] > 0
    assert data["costs"]["monthly_budget_usd"] == 25.0
    assert data["costs"]["tracked_monthly_estimate_usd"] == 5.0
    assert data["costs"]["current_month_cost_usd"] == 5.0
    assert data["costs"]["current_month_paid_usd"] == 2.0
    assert data["costs"]["current_outstanding_usd"] == 3.0
    assert data["costs"]["recorded_total_usd"] == 5.0
    assert data["costs"]["recorded_paid_usd"] == 2.0
    assert data["costs"]["recorded_outstanding_usd"] == 3.0
    assert data["costs"]["budget_utilization_percent"] == 12.0
    assert {item["id"] for item in data["costs"]["items"]} == {
        "r2",
        "railway",
        "neon",
        "azure_static_web_apps",
    }
    assert len(data["costs"]["history"]) == 12
    assert data["costs"]["history"][-2]["total_usd"] is None
    assert data["costs"]["history"][-2]["available"] is False
    assert data["costs"]["history"][-1]["provider_costs"]["Railway"] == 5.0
    assert data["costs"]["history"][-1]["paid_usd"] == 2.0
    assert data["costs"]["history"][-1]["outstanding_usd"] == 3.0
    assert data["costs"]["history"][-1]["available"] is True
    assert data["quotas"] == []
    assert data["refresh_after_seconds"] == 30


def test_infrastructure_cost_total_keeps_accrued_retired_azure_charges(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import infrastructure

    monkeypatch.setenv("AZURE_COST_MANAGEMENT_ENABLED", "true")
    monkeypatch.setenv("RAILWAY_MONTHLY_COST_USD", "5")
    monkeypatch.setenv("NEON_MONTHLY_COST_USD", "0")
    monkeypatch.setenv("FRONTEND_MONTHLY_COST_USD", "0")
    monkeypatch.setenv("INFRA_CURRENT_MONTH_PAID_USD", "0")
    monkeypatch.setattr(
        infrastructure,
        "_azure_month_to_date_costs",
        lambda _force_refresh: {
            "category_costs": {"frontend": 0.0, "private_dns": 0.03, "vnet": 0.15},
            "resource_ids": {"frontend": ["/staticSites/job-portal-web"]},
        },
    )

    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    response = client.get(
        "/api/admin/infrastructure?refresh=true",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 200
    costs = response.json()["costs"]
    assert costs["current_month_cost_usd"] == 5.18
    assert costs["current_outstanding_usd"] == 5.18
    assert costs["history"][-1]["provider_costs"]["Microsoft Azure"] == 0.18
    frontend = next(
        item for item in costs["items"] if item["id"] == "azure_static_web_apps"
    )
    assert frontend["monthly_estimate_usd"] == 0.0
    assert {item["id"] for item in costs["items"]} == {
        "r2",
        "railway",
        "neon",
        "azure_static_web_apps",
    }


def test_keyword_rank_list_aggregates_each_unique_keyword_across_urls(client: TestClient):
    from datetime import datetime, timedelta
    from app.models import SEOKeywordRank
    from app.services.seo_tools import list_keyword_ranks

    override = app.dependency_overrides[get_db]()
    db = next(override)
    try:
        now = datetime.utcnow()
        db.add_all(
            [
                SEOKeywordRank(
                    id="keyword-old",
                    keyword="PakJobs",
                    url="https://pakistanjobsmarket.com/",
                    position=9,
                    search_page=1,
                    impressions=100,
                    clicks=10,
                    recorded_at=now - timedelta(minutes=1),
                ),
                SEOKeywordRank(
                    id="keyword-new",
                    keyword="pakjobs",
                    url="https://pakistanjobsmarket.com",
                    position=7,
                    search_page=1,
                    impressions=10,
                    clicks=1,
                    recorded_at=now,
                ),
                SEOKeywordRank(
                    id="keyword-other-url",
                    keyword="  PAKJOBS  ",
                    url="https://pakistanjobsmarket.com/jobs/guide",
                    position=3,
                    search_page=1,
                    impressions=30,
                    clicks=3,
                    recorded_at=now + timedelta(seconds=1),
                ),
                SEOKeywordRank(
                    id="keyword-distinct",
                    keyword="Lahore jobs",
                    url="https://pakistanjobsmarket.com/tags/lahore",
                    position=8,
                    search_page=1,
                    impressions=2,
                    clicks=0,
                    recorded_at=now,
                ),
            ]
        )
        db.commit()
        rows = list_keyword_ranks(db, 100)
    finally:
        db.close()

    assert len(rows) == 2
    pakjobs = next(row for row in rows if row["keyword"].casefold() == "pakjobs")
    assert pakjobs["id"] == "keyword-other-url"
    assert pakjobs["url"] == "https://pakistanjobsmarket.com/jobs/guide"
    assert pakjobs["url_count"] == 2
    assert pakjobs["impressions"] == 40
    assert pakjobs["clicks"] == 4
    assert pakjobs["average_position"] == 4.0
    assert pakjobs["ctr"] == 0.1
    assert [row["keyword"].casefold() for row in rows] == ["pakjobs", "lahore jobs"]


def test_backlink_add_is_idempotent_and_existing_rows_are_deduplicated(client: TestClient):
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from app.models import SEOBacklink
    from app.services.seo_tools import add_backlink, list_backlinks

    override = app.dependency_overrides[get_db]()
    db = next(override)
    try:
        now = datetime.utcnow()
        db.add_all(
            [
                SEOBacklink(
                    id="backlink-old",
                    source_url="https://www.linkedin.com/company/pakistanjobsmarket/",
                    target_url="https://pakistanjobsmarket.com/",
                    anchor_text="old",
                    domain="www.linkedin.com",
                    first_seen=now - timedelta(days=2),
                    last_seen=now - timedelta(days=1),
                ),
                SEOBacklink(
                    id="backlink-new",
                    source_url="https://www.linkedin.com/company/pakistanjobsmarket",
                    target_url="https://pakistanjobsmarket.com",
                    anchor_text="new",
                    domain="www.linkedin.com",
                    first_seen=now - timedelta(days=1),
                    last_seen=now,
                ),
            ]
        )
        db.commit()

        assert len(list_backlinks(db)) == 1
        result = add_backlink(
            db,
            source_url="https://www.linkedin.com/company/pakistanjobsmarket/",
            target_url="https://pakistanjobsmarket.com/",
            anchor_text="linkedin_url",
        )
        stored = db.execute(select(SEOBacklink)).scalars().all()
    finally:
        db.close()

    assert result["created"] is False
    assert result["duplicates_removed"] == 1
    assert len(stored) == 1
    assert stored[0].anchor_text == "linkedin_url"


def test_url_search_performance_is_impression_weighted(client: TestClient):
    from datetime import datetime

    from app.models import SEOKeywordRank
    from app.services.seo_tools import entity_rank_summary

    override = app.dependency_overrides[get_db]()
    db = next(override)
    try:
        db.add_all(
            [
                SEOKeywordRank(
                    id="weighted-rank-one",
                    keyword="pak jobs",
                    url="https://pakistanjobsmarket.com/jobs/test",
                    position=2,
                    impressions=10,
                    clicks=1,
                    ctr=0.1,
                    recorded_at=datetime.utcnow(),
                ),
                SEOKeywordRank(
                    id="weighted-rank-two",
                    keyword="jobs pakistan",
                    url="https://pakistanjobsmarket.com/jobs/test",
                    position=10,
                    impressions=30,
                    clicks=3,
                    ctr=0.1,
                    recorded_at=datetime.utcnow(),
                ),
            ]
        )
        db.commit()
        rows = entity_rank_summary(db)
    finally:
        db.close()

    assert len(rows) == 1
    assert rows[0]["average_position"] == 8.0
    assert rows[0]["impressions"] == 40
    assert rows[0]["clicks"] == 4
    assert rows[0]["ctr"] == 0.1
    assert "search_page" not in rows[0]


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
        {
            "country": "Unknown",
            "region": None,
            "city": None,
            "visitors": 1,
            "page_views": 1,
        }
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


def test_qna_source_returns_comments_when_transcript_is_slow(
    monkeypatch: pytest.MonkeyPatch,
):
    import time
    from app.services import qna as qna_service

    def slow_transcript(_video_id: str):
        time.sleep(2)
        return "Late transcript content."

    monkeypatch.setattr(qna_service, "get_transcript", slow_transcript)
    monkeypatch.setattr(
        qna_service,
        "get_top_comments",
        lambda _video_id, **_kwargs: [
            "TOP-LEVEL COMMENT: What is the test pattern?\nREPLY 1: Pehle MCQs test hota hai."
        ],
    )

    started = time.monotonic()
    source = qna_service._collect_video_source(
        {
            "video_id": "video-1",
            "title": "FIA Inspector interview preparation",
            "url": "https://youtu.be/video-1",
        },
        video_index=1,
        max_comments=50,
        source_timeout_seconds=1.5,
    )

    assert source["comments"]
    assert time.monotonic() - started < 1.8


def test_qna_source_keeps_comments_that_finish_after_a_fast_transcript(
    monkeypatch: pytest.MonkeyPatch,
):
    import time
    from app.services import qna as qna_service

    monkeypatch.setattr(qna_service, "get_transcript", lambda _video_id: "Fast transcript.")

    def comments(_video_id: str, **_kwargs):
        time.sleep(1.05)
        return ["TOP-LEVEL COMMENT: What is the fee?\nREPLY 1: The fee is Rs. 500."]

    monkeypatch.setattr(qna_service, "get_top_comments", comments)
    source = qna_service._collect_video_source(
        {
            "video_id": "video-comments-after-transcript",
            "title": "FIA Inspector fee guide",
            "url": "https://youtu.be/video-comments-after-transcript",
        },
        video_index=1,
        max_comments=50,
        source_timeout_seconds=1.3,
    )

    assert source["transcript"] == "Fast transcript."
    assert source["comments"] == [
        "TOP-LEVEL COMMENT: What is the fee?\nREPLY 1: The fee is Rs. 500."
    ]


def test_qna_does_not_scan_beyond_the_five_recent_candidates_when_sources_are_empty(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import qna as qna_service

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
    searches: list[dict[str, object]] = []

    def search(*_args, **_kwargs):
        searches.append(_kwargs)
        return [{"video_id": "blocked", "title": "FIA Inspector interview", "url": "https://youtu.be/blocked"}]

    monkeypatch.setattr(qna_service, "search_youtube", search)
    monkeypatch.setattr(
        qna_service,
        "rank_by_similarity",
        lambda _title, rows, **_kwargs: [{**row, "title_similarity": 0.9} for row in rows],
    )
    monkeypatch.setattr(
        qna_service,
        "get_transcript",
        lambda _video_id: None,
    )
    monkeypatch.setattr(qna_service, "get_top_comments", lambda *_args, **_kwargs: [])
    result = qna_service.fetch_qna_for_job_title(
        db,
        job_id="fallback-job",
        job_title="FIA Inspector jobs in government",
    )

    assert len(searches) == 1
    assert searches[0]["max_results"] == 5
    assert searches[0]["raise_on_failure"] is True
    assert "could not be retrieved" in result["error"]
    assert result["count"] == 0
    assert result["videos_scanned"] == 1
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
    ranking: dict[str, object] = {}

    def search(*args, **kwargs):
        searched["query"] = args[0]
        searched.update(kwargs)
        return videos

    monkeypatch.setattr(qna_service, "search_youtube", search)
    def rank(*_args, **kwargs):
        ranking.update(kwargs)
        return [{**video, "title_similarity": 0.9} for video in videos]

    monkeypatch.setattr(qna_service, "rank_by_similarity", rank)
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
    assert searched["max_results"] == 5
    assert searched["raise_on_failure"] is True
    assert searched["query"] == "FIA Inspector"
    assert "raw_cosine_only" not in ranking
    assert ranking["preserve_order"] is True
    assert extracted_titles == [
        "FIA Inspector interview",
        "FIA Inspector preparation",
    ]
    assert db.query(JobQnA).filter(JobQnA.job_id == "job-first-match").count() == 1
    db.close()


def test_qna_runtime_options_override_default_threshold_videos_and_comments(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import qna as qna_service

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()
    captured: dict[str, object] = {}
    video = {
        "video_id": "nadra-runtime-options",
        "title": "NADRA Jobs 2026 | Deputy Assistant Director",
        "url": "https://youtu.be/nadra-runtime-options",
    }

    def search(query, **kwargs):
        captured["query"] = query
        captured["search"] = kwargs
        return [video]

    def collect(videos, **kwargs):
        captured["selected_videos"] = videos
        captured["collection"] = kwargs
        return [
            {
                **video,
                "video_index": 1,
                "title_similarity": 0.72,
                "transcript": "Candidates must submit the online application form.",
                "comments": [],
            }
        ]

    monkeypatch.setattr(qna_service, "search_youtube", search)
    monkeypatch.setattr(
        qna_service,
        "rank_by_similarity",
        lambda _title, rows, **_kwargs: [{**rows[0], "title_similarity": 0.72}],
    )
    monkeypatch.setattr(qna_service, "_collect_video_sources", collect)
    monkeypatch.setattr(
        qna_service,
        "extract_qna_from_sources",
        lambda **_kwargs: [
            {
                "question": "How must candidates apply?",
                "answer": "Candidates must submit the online application form.",
                "source": "transcript",
                "video_index": 1,
            }
        ],
    )

    result = qna_service.fetch_qna_for_job_title(
        db,
        job_id="nadra-runtime-options",
        job_title="NADRA Jobs 2026 – Deputy Assistant Director (Technical) | Apply Online",
        min_similarity_percent=70,
        youtube_video_count=12,
        comments_per_video=75,
    )

    assert result["count"] == 1
    assert captured["query"] == "NADRA 2026 Deputy Assistant Director (Technical)"
    assert captured["search"]["max_results"] == 12
    assert captured["collection"]["max_comments"] == 75
    assert len(captured["selected_videos"]) == 1
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


def test_qna_requires_source_evidence_and_keeps_distinct_intents_per_topic(
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
    assert "English, Urdu, Roman Urdu" in captured["system"]
    assert [row["topic"] for row in rows] == [
        "age_eligibility",
        "age_eligibility",
        "education_eligibility",
    ]
    assert rows[0]["answer"] == "Applicants must be between 18 and 30 years old."
    assert rows[1]["answer"] == "A five-year age relaxation applies."
    assert rows[2]["answer"] == "The required qualification is a bachelor's degree."
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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Maybe the screening test will be held in July.", True),
        ("Shayad July mein test ho ga.", True),
        ("The screening test will be held on 15 July.", False),
    ],
)
def test_qna_detects_uncertain_answers(value: str, expected: bool):
    from app.services.qna import _answer_is_uncertain

    assert _answer_is_uncertain(value) is expected


def test_qna_keeps_distinct_english_and_roman_urdu_intents_within_one_topic(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import qna as qna_service

    maximum_age = "Inspector FIA ki maximum age limit 30 years hai."
    relaxation = "Yes, candidates receive five years of general age relaxation."

    def completion(_messages, **_kwargs):
        return json.dumps(
            {
                "qna": [
                    {
                        "question": "What is the maximum age for Inspector FIA?",
                        "answer": maximum_age,
                        "answer_evidence": maximum_age,
                        "topic": "age_eligibility",
                        "video_index": 1,
                    },
                    {
                        "question": "Is general age relaxation available?",
                        "answer": relaxation,
                        "answer_evidence": relaxation,
                        "topic": "age_eligibility",
                        "video_index": 1,
                    },
                    {
                        "question": "Can a 31 year old apply?",
                        "answer": "Sir 31 saal ki age mein apply kar sakte hain kya?",
                        "answer_evidence": "Sir 31 saal ki age mein apply kar sakte hain kya?",
                        "topic": "age_eligibility",
                        "video_index": 1,
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
                "title": "FIA Inspector eligibility Q&A",
                "title_similarity": 0.9,
                "transcript": maximum_age,
                "comments": [
                    "TOP-LEVEL COMMENT: Is age relaxation available?\n"
                    f"REPLY 1: {relaxation}",
                    "TOP-LEVEL COMMENT: Sir 31 saal ki age mein apply kar sakte hain kya?",
                ],
            }
        ],
        max_qna=20,
        timeout_seconds=10,
    )

    assert [row["answer"] for row in rows] == [maximum_age, relaxation]
    assert all("apply kar sakte" not in row["answer"] for row in rows)


def test_youtube_api_preserves_comment_questions_with_their_replies(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import youtube

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "items": [
                    {
                        "snippet": {
                            "totalReplyCount": 1,
                            "topLevelComment": {
                                "id": "roman-thread",
                                "snippet": {
                                    "textDisplay": "Sir age relaxation milti hai?"
                                },
                            },
                        },
                        "replies": {
                            "comments": [
                                {
                                    "snippet": {
                                        "textDisplay": "Jee, 5 years relaxation milti hai."
                                    }
                                }
                            ]
                        },
                    },
                    {
                        "snippet": {
                            "totalReplyCount": 1,
                            "topLevelComment": {
                                "id": "english-thread",
                                "snippet": {"textDisplay": "What is the test pattern?"},
                            },
                        },
                        "replies": {
                            "comments": [
                                {
                                    "snippet": {
                                        "textDisplay": "It starts with an MCQ test."
                                    }
                                }
                            ]
                        },
                    },
                ]
            }

    monkeypatch.setattr(youtube.httpx, "get", lambda *_args, **_kwargs: Response())
    rows = youtube._comments_api("video", 50, 10)

    assert rows == [
        "TOP-LEVEL COMMENT: Sir age relaxation milti hai?\n"
        "REPLY 1: Jee, 5 years relaxation milti hai.",
        "TOP-LEVEL COMMENT: What is the test pattern?\n"
        "REPLY 1: It starts with an MCQ test.",
    ]


def test_youtube_api_fetches_every_paginated_reply_in_each_selected_thread(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import youtube

    class Response:
        def __init__(self, payload: dict):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    reply_pages = [
        {
            "items": [
                {"snippet": {"textDisplay": "First complete answer."}},
                {"snippet": {"textDisplay": "Second supporting answer."}},
            ],
            "nextPageToken": "next-replies",
        },
        {"items": [{"snippet": {"textDisplay": "Final reply."}}]},
    ]

    def get(url: str, **_kwargs):
        if url.endswith("/commentThreads"):
            return Response(
                {
                    "items": [
                        {
                            "snippet": {
                                "totalReplyCount": 3,
                                "topLevelComment": {
                                    "id": "thread-with-pages",
                                    "snippet": {"textDisplay": "How does selection work?"},
                                },
                            },
                            "replies": {
                                "comments": [
                                    {"snippet": {"textDisplay": "Embedded partial reply."}}
                                ]
                            },
                        }
                    ]
                }
            )
        return Response(reply_pages.pop(0))

    monkeypatch.setattr(youtube.httpx, "get", get)
    rows = youtube._comments_api("video", 50, 10)

    assert rows == [
        "TOP-LEVEL COMMENT: How does selection work?\n"
        "REPLY 1: First complete answer.\n"
        "REPLY 2: Second supporting answer.\n"
        "REPLY 3: Final reply."
    ]
    assert not reply_pages


def test_youtube_api_paginates_beyond_the_old_fifty_comment_cap(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import youtube

    class Response:
        def __init__(self, payload: dict):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    calls: list[dict] = []

    def get(url: str, **kwargs):
        assert url.endswith("/commentThreads")
        calls.append(kwargs["params"].copy())
        start = 0 if len(calls) == 1 else 60
        count = 60 if len(calls) == 1 else 15
        return Response(
            {
                "items": [
                    {
                        "snippet": {
                            "totalReplyCount": 0,
                            "topLevelComment": {
                                "id": f"thread-{index}",
                                "snippet": {"textDisplay": f"Comment {index}"},
                            },
                        }
                    }
                    for index in range(start, start + count)
                ],
                **({"nextPageToken": "second-page"} if len(calls) == 1 else {}),
            }
        )

    monkeypatch.setattr(youtube.httpx, "get", get)
    rows = youtube._comments_api("video", 75, 10)

    assert len(rows) == 75
    assert calls[0]["maxResults"] == 75
    assert calls[1]["maxResults"] == 15
    assert calls[1]["pageToken"] == "second-page"


def test_ytdlp_transcript_fallback_reads_generated_json3(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    from app.services import youtube

    class TemporaryDirectory:
        def __init__(self, **_kwargs):
            self.path = tmp_path

        def __enter__(self):
            return str(self.path)

        def __exit__(self, *_args):
            return None

    def run(command, **_kwargs):
        output_pattern = command[command.index("--output") + 1]
        path = Path(output_pattern.replace("%(id)s", "video").replace("%(ext)s", "en.json3"))
        path.write_text(
            json.dumps(
                {
                    "events": [
                        {"segs": [{"utf8": "Inspector FIA age limit "}]},
                        {"segs": [{"utf8": "30 years hai."}]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(youtube.tempfile, "TemporaryDirectory", TemporaryDirectory)
    monkeypatch.setattr(youtube.subprocess, "run", run)

    assert youtube._transcript_ytdlp("video", timeout_seconds=10) == (
        "Inspector FIA age limit 30 years hai."
    )


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
            "model_label": "DeepSeek-V4-Pro-0813",
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
    assert payloads[0]["model"] == "deepseek-v4-pro"
    assert payloads[0]["thinking"] == {"type": "disabled"}
    assert payloads[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in payloads[1]


def test_qna_production_config_matches_the_requested_pipeline_contract():
    from app.config import load_config

    load_config.cache_clear()
    config = load_config()
    task = config["llm"]["tasks"]["qna_extraction"]
    youtube = config["youtube_qna"]

    assert task["provider"] == "deepseek"
    assert task["model"] == "DeepSeek-V4-Pro-0813"
    assert task["api_model"] == "deepseek-v4-pro"
    assert youtube["max_youtube_search_results"] == 5
    assert youtube["max_youtube_videos"] == 5
    assert youtube["min_title_similarity"] == 0.8
    assert "timeout_seconds" not in youtube
    assert youtube["max_comments"] == 50
    assert youtube["max_qna"] == 20


def test_requested_deepseek_release_uses_the_official_api_model_id(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services.llm import resolve_task_llm

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-production-looking-test-key")
    resolved = resolve_task_llm("qna_extraction")

    assert resolved["provider"] == "deepseek"
    assert resolved["model_label"] == "DeepSeek-V4-Pro-0813"
    assert resolved["model"] == "deepseek-v4-pro"


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
            "provinces": ["Sindh"],
            "source": "Acme Pvt Ltd",
            "education_required": "BS Computer Science",
            "tags": ["Software Engineering"],
        },
    )
    assert created.status_code == 200
    slug = created.json()["slug"]
    sitemap = client.get("/api/sitemap-data")
    assert sitemap.status_code == 200
    urls = {url["loc"] for url in sitemap.json()["urls"]}
    assert any(url.endswith(f"/jobs/{slug}") for url in urls)
    assert any(url.endswith("/locations/karachi") for url in urls)
    assert any(url.endswith("/locations/sindh") for url in urls)
    assert any(url.endswith("/companies/acme-pvt-ltd") for url in urls)
    assert any(url.endswith("/qualifications/bs-computer-science") for url in urls)
    assert any(url.endswith("/categories/software-engineering") for url in urls)
    assert any(url.endswith("/tags/software-engineering") for url in urls)


def test_sitemap_data_only_includes_published_custom_pages(client: TestClient):
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    published = client.post(
        "/api/admin/pages",
        headers=auth,
        json={
            "title": "Published Resource",
            "slug": "published-resource",
            "content": "<p>Useful public content.</p>",
            "is_published": True,
        },
    )
    draft = client.post(
        "/api/admin/pages",
        headers=auth,
        json={
            "title": "Private Draft",
            "slug": "private-draft",
            "content": "<p>Not ready for search.</p>",
            "is_published": False,
        },
    )
    assert published.status_code == 200
    assert draft.status_code == 200

    urls = {
        item["loc"]
        for item in client.get("/api/sitemap-data").json()["urls"]
    }
    assert any(url.endswith("/p/published-resource") for url in urls)
    assert not any(url.endswith("/p/private-draft") for url in urls)


def test_blog_crud_filters_seo_pagination_and_sitemap(client: TestClient):
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin-password"}
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    article_content = (
        "<h2>Preparation</h2>"
        "<p>Build a focused study plan for FPSC exams.</p>"
        "<table><thead><tr><th>Stage</th><th>Focus</th></tr></thead>"
        "<tbody><tr><td>Screening</td><td>Past papers</td></tr></tbody></table>"
    )
    published = client.post(
        "/api/admin/blog",
        headers=auth,
        json={
            "slug": "how-to-prepare-for-fpsc",
            "title": "How to Prepare for FPSC Jobs",
            "excerpt": "A practical preparation guide.",
            "content": article_content,
            "author": "PakistanJobs Editorial Team",
            "category": "Career Advice",
            "tags": ["FPSC", "Exam Preparation"],
            "is_published": True,
            "published_at": "2026-07-18T12:00:00",
            "seo": {
                "focus_keyword": "FPSC preparation",
                "meta_title": "How to Prepare for FPSC Jobs",
                "meta_description": "A focused FPSC preparation guide for candidates in Pakistan.",
            },
        },
    )
    assert published.status_code == 200, published.text
    post = published.json()

    admin_detail = client.get(f"/api/admin/blog/{post['id']}", headers=auth)
    assert admin_detail.status_code == 200
    assert admin_detail.json()["title"] == "How to Prepare for FPSC Jobs"
    assert admin_detail.json()["excerpt"] == "A practical preparation guide."
    assert admin_detail.json()["content"] == article_content
    assert admin_detail.json()["author"] == "PakistanJobs Editorial Team"
    assert admin_detail.json()["category"] == "Career Advice"
    assert admin_detail.json()["tags"] == ["FPSC", "Exam Preparation"]

    draft = client.post(
        "/api/admin/blog",
        headers=auth,
        json={
            "slug": "private-draft",
            "title": "Private Draft",
            "content": "<p>Not public yet.</p>",
            "tags": [],
            "is_published": False,
        },
    )
    assert draft.status_code == 200

    public = client.get("/api/blog?q=prepare&category=Career%20Advice&tag=FPSC&page=1&page_size=1")
    assert public.status_code == 200
    assert public.json()["total"] == 1
    assert public.json()["items"][0]["slug"] == post["slug"]
    assert all(item["slug"] != "private-draft" for item in public.json()["items"])

    filters = client.get("/api/blog/filters")
    assert filters.status_code == 200
    assert "Career Advice" in filters.json()["categories"]
    assert "FPSC" in filters.json()["tags"]

    detail = client.get(f"/api/blog/{post['slug']}")
    assert detail.status_code == 200
    assert detail.json()["author"] == "PakistanJobs Editorial Team"
    assert detail.json()["content"] == article_content
    assert client.get("/api/blog/private-draft").status_code == 404

    seo = client.get(f"/api/seo/blog/{post['id']}")
    assert seo.status_code == 200
    assert seo.json()["entity_type"] == "blog"
    assert seo.json()["focus_keyword"] == "FPSC preparation"
    assert seo.json()["structured_data"]["@type"] == "BlogPosting"

    updated = client.put(
        f"/api/admin/blog/{post['id']}",
        headers=auth,
        json={"title": "FPSC Preparation Guide", "tags": ["FPSC", "Interview"]},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "FPSC Preparation Guide"

    admin = client.get("/api/admin/blog?status=draft", headers=auth)
    assert admin.status_code == 200
    assert admin.json()["total"] == 1
    assert admin.json()["items"][0]["slug"] == "private-draft"

    sitemap = client.get("/api/sitemap-data")
    sitemap_urls = {url["loc"] for url in sitemap.json()["urls"]}
    assert any(url.endswith(f"/blog/{post['slug']}") for url in sitemap_urls)
    assert any(url.endswith("/blog/categories/career-advice") for url in sitemap_urls)
    assert any(url.endswith("/blog/tags/fpsc") for url in sitemap_urls)

    deleted = client.delete(f"/api/admin/blog/{post['id']}", headers=auth)
    assert deleted.status_code == 200
    assert client.get(f"/api/seo/blog/{post['id']}").json() is None
    assert client.get(f"/api/blog/{post['slug']}").status_code == 404


def test_blog_admin_routes_require_authentication(client: TestClient):
    assert client.get("/api/admin/blog").status_code == 401
    assert client.post(
        "/api/admin/blog",
        json={"slug": "blocked", "title": "Blocked", "content": "", "tags": []},
    ).status_code == 401
