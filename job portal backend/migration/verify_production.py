#!/usr/bin/env python3
"""Run reversible production smoke and CRUD checks.

The script never prints credentials or response bodies. By default it reads the
admin username/password from the environment. During the Azure-to-Railway
cutover it can resolve those two values from the rollback Container App so the
operator does not need to copy production credentials into a shell command.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from export_railway_env import _resolved_azure_variables


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


class API:
    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token: str | None = None

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        headers = {"Accept": "application/json"}
        body = None
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                status = response.status
                raw = response.read()
                content_type = response.headers.get("content-type", "")
        except HTTPError as exc:
            status = exc.code
            raw = exc.read()
            content_type = exc.headers.get("content-type", "")
        except URLError as exc:
            raise RuntimeError(f"{method} {path}: network error: {exc.reason}") from exc
        if status not in expected:
            raise RuntimeError(f"{method} {path}: expected {expected}, received {status}")
        if not raw:
            return None
        if "json" in content_type:
            return json.loads(raw)
        return raw.decode("utf-8", errors="replace")

    def upload(
        self,
        path: str,
        *,
        filename: str,
        content_type: str,
        data: bytes,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        boundary = f"codex-{uuid4().hex}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                status = response.status
                raw = response.read()
                response_type = response.headers.get("content-type", "")
        except HTTPError as exc:
            status = exc.code
            raw = exc.read()
            response_type = exc.headers.get("content-type", "")
        except URLError as exc:
            raise RuntimeError(f"POST {path}: network error: {exc.reason}") from exc
        if status not in expected:
            raise RuntimeError(f"POST {path}: expected {expected}, received {status}")
        if not raw:
            return None
        if "json" in response_type:
            return json.loads(raw)
        return raw.decode("utf-8", errors="replace")


def _record(checks: list[Check], name: str, action: Any) -> Any:
    started = time.monotonic()
    try:
        value = action()
    except Exception as exc:
        checks.append(Check(name, False, str(exc)))
        return None
    elapsed = time.monotonic() - started
    checks.append(Check(name, True, f"{elapsed:.2f}s"))
    return value


def _credentials(args: argparse.Namespace) -> tuple[str, str]:
    username = os.getenv("ADMIN_USERNAME", "")
    password = os.getenv("ADMIN_PASSWORD", "")
    if username and password:
        return username, password
    if not args.azure_credentials:
        raise RuntimeError(
            "Set ADMIN_USERNAME and ADMIN_PASSWORD or pass --azure-credentials"
        )
    variables, _ = _resolved_azure_variables(
        resource_group=args.azure_resource_group,
        container_app=args.azure_container_app,
    )
    username = variables.get("ADMIN_USERNAME", "")
    password = variables.get("ADMIN_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("Admin credentials were not found in the Azure Container App")
    return username, password


def _read_checks(api: API, site_url: str, checks: list[Check]) -> None:
    for name, path in [
        ("API root", "/"),
        ("Liveness", "/health"),
        ("Readiness", "/ready"),
        ("Jobs list", "/api/jobs?page=1&page_size=3"),
        ("Filters", "/api/filters"),
        ("Statistics", "/api/stats"),
        ("Public taxonomy", "/api/taxonomy"),
        ("Blog list", "/api/blog?page=1&page_size=3"),
        ("Blog filters", "/api/blog/filters"),
        ("Public pages", "/api/pages"),
        ("Branding", "/api/settings/branding"),
        ("Social settings", "/api/settings/social"),
        ("Sitemap data", "/api/sitemap-data"),
    ]:
        _record(checks, name, lambda path=path: api.request("GET", path))

    site = API(site_url)
    for name, path in [
        ("Frontend home", "/"),
        ("Frontend jobs", "/"),
        ("Frontend blog", "/blog"),
        ("Resume Builder", "/resume-builder"),
        ("Cover Letter", "/cover-letter"),
        ("Contact page", "/contact"),
        ("About page", "/about"),
        ("Privacy page", "/privacy"),
        ("Disclaimer page", "/disclaimer"),
        ("robots.txt", "/robots.txt"),
        ("sitemap.xml", "/sitemap.xml"),
        ("ads.txt", "/ads.txt"),
    ]:
        _record(checks, name, lambda path=path: site.request("GET", path))


def _admin_checks(api: API, checks: list[Check]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name, key, path in [
        ("Admin identity", "me", "/api/auth/me"),
        ("Admin blog", "blog", "/api/admin/blog?page=1&page_size=3"),
        ("Admin pages", "pages", "/api/admin/pages"),
        ("Admin messages", "messages", "/api/admin/contact"),
        ("Admin taxonomy", "taxonomy", "/api/admin/taxonomy"),
        ("Newsletter", "newsletter", "/api/admin/subscriptions"),
        ("Analytics realtime", "realtime", "/api/admin/analytics/realtime"),
        ("Analytics dashboard", "analytics", "/api/admin/analytics"),
        ("Infrastructure", "infrastructure", "/api/admin/infrastructure"),
        ("SEO dashboard", "seo_dashboard", "/api/admin/seo/dashboard"),
        ("SEO metadata", "seo_meta", "/api/admin/seo"),
        ("SEO social", "social", "/api/admin/seo/social"),
        ("SEO backlinks", "backlinks", "/api/admin/seo/backlinks"),
        ("Admin branding", "branding", "/api/admin/settings/branding"),
    ]:
        values[key] = _record(
            checks, name, lambda path=path: api.request("GET", path)
        )
    return values


def _crud_checks(api: API, checks: list[Check], current: dict[str, Any]) -> None:
    marker = uuid4().hex[:12]
    blog_id: str | None = None
    page_id: str | None = None
    taxonomy_id: str | None = None
    contact_id: str | None = None
    upload_key: str | None = None
    try:
        # A valid 1x1 PNG exercises the same R2 path as a clipboard/editor
        # image. The object is deleted in finally, even if a later check fails.
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
            "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        )
        upload = _record(
            checks,
            "Editor image upload",
            lambda: api.upload(
                "/api/admin/upload",
                filename=f"codex-smoke-{marker}.png",
                content_type="image/png",
                data=png,
            ),
        )
        upload_key = upload.get("s3_path") if isinstance(upload, dict) else None

        blog = _record(
            checks,
            "Blog create draft",
            lambda: api.request(
                "POST",
                "/api/admin/blog",
                json_body={
                    "slug": f"codex-smoke-blog-{marker}",
                    "title": f"Codex smoke blog {marker}",
                    "content": "<p>Temporary production CRUD verification.</p>",
                    "tags": ["codex-smoke"],
                    "is_published": False,
                },
            ),
        )
        blog_id = blog.get("id") if isinstance(blog, dict) else None
        if blog_id:
            _record(
                checks,
                "Blog update draft",
                lambda: api.request(
                    "PUT",
                    f"/api/admin/blog/{blog_id}",
                    json_body={"excerpt": "Updated temporary CRUD verification."},
                ),
            )
            _record(
                checks,
                "Blog read draft",
                lambda: api.request("GET", f"/api/admin/blog/{blog_id}"),
            )

        page = _record(
            checks,
            "Page create unpublished",
            lambda: api.request(
                "POST",
                "/api/admin/pages",
                json_body={
                    "slug": f"codex-smoke-page-{marker}",
                    "title": f"Codex smoke page {marker}",
                    "content": "<p>Temporary production CRUD verification.</p>",
                    "is_published": False,
                },
            ),
        )
        page_id = page.get("id") if isinstance(page, dict) else None
        if page_id:
            _record(
                checks,
                "Page update unpublished",
                lambda: api.request(
                    "PUT",
                    f"/api/admin/pages/{page_id}",
                    json_body={"title": f"Codex smoke page updated {marker}"},
                ),
            )
            _record(
                checks,
                "Unpublished page remains private",
                lambda: api.request(
                    "GET",
                    f"/api/pages/codex-smoke-page-{marker}",
                    expected=(404,),
                ),
            )

        term = _record(
            checks,
            "Taxonomy create inactive",
            lambda: api.request(
                "POST",
                "/api/admin/taxonomy",
                json_body={
                    "name": f"Codex Smoke {marker}",
                    "slug": f"codex-smoke-{marker}",
                    "kind": "tag",
                    "is_active": False,
                },
            ),
        )
        taxonomy_id = term.get("id") if isinstance(term, dict) else None
        if taxonomy_id:
            _record(
                checks,
                "Taxonomy update inactive",
                lambda: api.request(
                    "PUT",
                    f"/api/admin/taxonomy/{taxonomy_id}",
                    json_body={"name": f"Codex Smoke Updated {marker}"},
                ),
            )

        contact = _record(
            checks,
            "Contact create",
            lambda: api.request(
                "POST",
                "/api/contact",
                json_body={
                    "name": "Codex Smoke",
                    "email": f"codex.smoke.{marker}@gmail.com",
                    "subject": "CRUD verification",
                    "message": "Temporary message created by the deployment verification.",
                },
                expected=(200,),
            ),
        )
        contact_id = contact.get("id") if isinstance(contact, dict) else None
        if contact_id:
            _record(
                checks,
                "Contact read and mark read",
                lambda: api.request("GET", f"/api/admin/contact/{contact_id}"),
            )

        branding = current.get("branding")
        if isinstance(branding, dict):
            allowed = {
                key: branding[key]
                for key in [
                    "site_name",
                    "site_title",
                    "site_title_alignment",
                    "site_header",
                    "site_description",
                    "footer_copyright",
                    "homepage_focus_keyword",
                    "homepage_meta_title",
                    "homepage_meta_description",
                    "homepage_meta_keywords",
                ]
                if key in branding
            }
            _record(
                checks,
                "Branding no-op update",
                lambda: api.request(
                    "PUT", "/api/admin/settings/branding", json_body=allowed
                ),
            )

        social = current.get("social")
        if isinstance(social, dict):
            _record(
                checks,
                "Social settings no-op update",
                lambda: api.request(
                    "PUT", "/api/admin/seo/social", json_body=social
                ),
            )

        newsletter = current.get("newsletter")
        if isinstance(newsletter, dict):
            _record(
                checks,
                "Newsletter template no-op update",
                lambda: api.request(
                    "PUT",
                    "/api/admin/subscriptions/template",
                    json_body={
                        "subject_template": newsletter["subject_template"],
                        "body_template": newsletter["body_template"],
                    },
                ),
            )

        _record(
            checks,
            "Yoast analysis",
            lambda: api.request(
                "POST",
                "/api/admin/seo/yoast/analyze",
                json_body={
                    "title": "Temporary SEO verification",
                    "content": "<h2>Verification</h2><p>Temporary content.</p>",
                    "focus_keyword": "verification",
                    "slug": "temporary-verification",
                },
            ),
        )
        _record(
            checks,
            "Analytics visit ingestion",
            lambda: api.request(
                "POST",
                "/api/analytics/visit",
                json_body={
                    "visitor_id": f"codex-smoke-{marker}",
                    "path": "/__deployment-smoke__",
                },
                expected=(201,),
            ),
        )
    finally:
        if upload_key:
            _record(
                checks,
                "Editor image delete",
                lambda: api.request(
                    "DELETE",
                    f"/api/admin/upload?{urlencode({'object_key': upload_key})}",
                ),
            )
        if contact_id:
            _record(
                checks,
                "Contact delete",
                lambda: api.request("DELETE", f"/api/admin/contact/{contact_id}"),
            )
        if taxonomy_id:
            _record(
                checks,
                "Taxonomy delete",
                lambda: api.request(
                    "DELETE", f"/api/admin/taxonomy/{taxonomy_id}"
                ),
            )
        if page_id:
            _record(
                checks,
                "Page delete",
                lambda: api.request("DELETE", f"/api/admin/pages/{page_id}"),
            )
        if blog_id:
            _record(
                checks,
                "Blog delete",
                lambda: api.request("DELETE", f"/api/admin/blog/{blog_id}"),
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-url", default="https://api.pakistanjobsmarket.com"
    )
    parser.add_argument(
        "--site-url", default="https://www.pakistanjobsmarket.com"
    )
    parser.add_argument("--azure-credentials", action="store_true")
    parser.add_argument(
        "--azure-resource-group", default="job-portal-prod-rg"
    )
    parser.add_argument("--azure-container-app", default="job-portal-api")
    parser.add_argument(
        "--public-only",
        action="store_true",
        help="run unauthenticated service checks without attempting an admin login",
    )
    args = parser.parse_args()

    checks: list[Check] = []
    api = API(args.api_url)
    _read_checks(api, args.site_url, checks)

    if not args.public_only:
        access_token = os.getenv("ADMIN_ACCESS_TOKEN", "").strip()
        if access_token:
            api.token = access_token
            _record(checks, "Admin token", lambda: api.request("GET", "/api/auth/me"))
        else:
            username, password = _credentials(args)
            login = _record(
                checks,
                "Admin login",
                lambda: api.request(
                    "POST",
                    "/api/auth/login",
                    json_body={"username": username, "password": password},
                ),
            )
            if isinstance(login, dict) and login.get("access_token"):
                api.token = str(login["access_token"])
        if api.token:
            current = _admin_checks(api, checks)
            _crud_checks(api, checks, current)

    print("Production service and CRUD verification")
    print("=" * 42)
    for check in checks:
        symbol = "PASS" if check.ok else "FAIL"
        print(f"{symbol:4}  {check.name:<38} {check.detail}")
    failed = [check for check in checks if not check.ok]
    print("-" * 42)
    print(f"{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        print(
            "Not exercised in production: publishing a job/newsletter send, "
            "password reset/change, logo replacement, backlink creation, and "
            "Search Console sync. Their automated tests remain the safety gate."
        )
    elif args.public_only:
        print("Authenticated admin CRUD was intentionally skipped (--public-only).")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
