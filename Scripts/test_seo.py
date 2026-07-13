#!/usr/bin/env python3
from __future__ import annotations

import argparse
import uuid

import httpx

from common import (
    CheckFailed,
    add_backend_to_path,
    admin_headers,
    api_base,
    require_response,
    run,
    site_base,
)


def _check_frontend(client: httpx.Client) -> None:
    home = require_response(client.get(f"{site_base()}/"), "frontend home page").text.lower()
    for marker in ("<title", 'name="description"', 'property="og:title"', 'name="robots"'):
        if marker not in home:
            raise CheckFailed(f"frontend home page is missing SEO marker {marker}")

    robots = require_response(client.get(f"{site_base()}/robots.txt"), "frontend robots.txt").text
    robots_lower = robots.lower()
    if "user-agent:" not in robots_lower or "sitemap:" not in robots_lower:
        raise CheckFailed("frontend robots.txt is missing crawler or sitemap directives")
    sitemap = require_response(client.get(f"{site_base()}/sitemap.xml"), "frontend sitemap.xml").text
    if "<urlset" not in sitemap or "<loc>" not in sitemap:
        raise CheckFailed("frontend sitemap.xml is not a populated XML sitemap")


def _cleanup_backlink(backlink_id: str) -> None:
    add_backend_to_path()
    from app.database import SessionLocal
    from app.models import SEOBacklink

    db = SessionLocal()
    try:
        row = db.get(SEOBacklink, backlink_id)
        if row:
            db.delete(row)
            db.commit()
    finally:
        db.close()


def check() -> str:
    parser = argparse.ArgumentParser(description="Exercise public, admin, and frontend SEO functionality.")
    parser.add_argument("--skip-external", action="store_true", help="Skip PageSpeed, GSC, and backlink discovery.")
    args = parser.parse_args()

    tested: list[str] = []
    test_backlink_id: str | None = None
    try:
        with httpx.Client(timeout=90.0, follow_redirects=True) as client:
            _check_frontend(client)
            tested.extend(["metadata", "robots", "sitemap"])

            backend_robots = require_response(client.get(f"{api_base()}/robots.txt"), "backend robots.txt")
            if "Disallow: /admin" not in backend_robots.text:
                raise CheckFailed("backend robots.txt does not protect admin routes")
            backend_sitemap = require_response(client.get(f"{api_base()}/sitemap.xml"), "backend sitemap.xml")
            if "<urlset" not in backend_sitemap.text:
                raise CheckFailed("backend sitemap.xml is invalid")
            sitemap_data = require_response(client.get(f"{api_base()}/api/sitemap-data"), "sitemap data").json()
            if not isinstance(sitemap_data.get("urls"), list):
                raise CheckFailed("sitemap data did not return a URL list")

            headers = admin_headers(client)
            seo_rows = require_response(client.get(f"{api_base()}/api/admin/seo", headers=headers), "SEO metadata list").json()
            dashboard = require_response(
                client.get(f"{api_base()}/api/admin/seo/dashboard", headers=headers), "SEO dashboard"
            ).json()
            for key in ("on_page", "off_page", "performance", "authority"):
                if key not in dashboard:
                    raise CheckFailed(f"SEO dashboard is missing {key}")
            tested.extend(["dashboard", "SEO metadata"])

            social = require_response(
                client.get(f"{api_base()}/api/admin/seo/social", headers=headers), "social settings"
            ).json()
            require_response(
                client.put(f"{api_base()}/api/admin/seo/social", headers=headers, json=social),
                "idempotent social settings update",
            )
            require_response(client.get(f"{api_base()}/api/settings/social"), "public social settings")
            tested.append("social settings")

            yoast = require_response(
                client.post(
                    f"{api_base()}/api/admin/seo/yoast/analyze",
                    headers=headers,
                    json={
                        "title": "Python Developer Jobs in Pakistan",
                        "content": "<h1>Python Developer Jobs</h1><p>Apply for Python developer jobs in Pakistan with complete requirements and application details.</p>",
                        "meta_title": "Python Developer Jobs in Pakistan",
                        "meta_description": "Find Python developer jobs in Pakistan and review requirements before applying.",
                        "focus_keyword": "Python developer jobs",
                        "slug": "python-developer-jobs-pakistan",
                    },
                ),
                "Yoast analysis",
            ).json()
            if not isinstance(yoast, dict) or not yoast:
                raise CheckFailed("Yoast analysis returned no result")
            tested.append("Yoast analysis")

            source_url = f"https://seo-diagnostic.invalid/{uuid.uuid4().hex}"
            backlink = require_response(
                client.post(
                    f"{api_base()}/api/admin/seo/backlinks",
                    headers=headers,
                    json={"source_url": source_url, "anchor_text": "SEO diagnostic", "notes": "temporary automated check"},
                ),
                "backlink creation",
            ).json()
            test_backlink_id = backlink.get("id")
            if not test_backlink_id:
                raise CheckFailed("backlink creation returned no ID")
            backlinks = require_response(
                client.get(f"{api_base()}/api/admin/seo/backlinks", headers=headers), "backlink list"
            ).json()
            if not any(row.get("id") == test_backlink_id for row in backlinks):
                raise CheckFailed("new backlink was not present in the backlink list")
            tested.append("backlinks")

            if seo_rows:
                row = seo_rows[0]
                require_response(
                    client.get(f"{api_base()}/api/seo/{row['entity_type']}/{row['entity_id']}"),
                    "public entity SEO",
                )
                tested.append("public entity SEO")

            if not args.skip_external:
                require_response(
                    client.post(f"{api_base()}/api/admin/seo/pagespeed", headers=headers), "PageSpeed check"
                )
                require_response(
                    client.post(f"{api_base()}/api/admin/seo/gsc/sync", headers=headers), "Search Console sync"
                )
                require_response(
                    client.post(f"{api_base()}/api/admin/seo/backlinks/discover", headers=headers),
                    "backlink discovery",
                )
                tested.extend(["PageSpeed", "Search Console", "backlink discovery"])
    finally:
        if test_backlink_id:
            _cleanup_backlink(test_backlink_id)
    return f"SEO checks passed: {', '.join(tested)}"


if __name__ == "__main__":
    raise SystemExit(run(check))
