from __future__ import annotations

import argparse
from urllib.parse import urlparse

import httpx

from common import CheckFailed, admin_headers, api_base, require_response, run

CORE_SLUGS = {"about", "contact", "privacy", "disclaimer"}
DEFAULT_PRODUCTION_API = "https://job-portal-api.bluefield-91b21860.centralindia.azurecontainerapps.io"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy production CMS pages into the local backend.")
    parser.add_argument("--source", default=DEFAULT_PRODUCTION_API)
    parser.add_argument("--target", default=api_base())
    parser.add_argument("--allow-remote-target", action="store_true")
    return parser.parse_args()


def check() -> str:
    args = parse_args()
    target_host = (urlparse(args.target).hostname or "").lower()
    if target_host not in {"localhost", "127.0.0.1", "backend"} and not args.allow_remote_target:
        raise CheckFailed("Refusing to overwrite a non-local target without --allow-remote-target")
    if args.target.rstrip("/") != api_base():
        raise CheckFailed("--target must match API_BASE_URL so local admin authentication is safe")

    with httpx.Client(timeout=30) as client:
        source = require_response(client.get(f"{args.source.rstrip('/')}/api/pages"), "production pages")
        production_pages = {page["slug"]: page for page in source.json() if page.get("slug") in CORE_SLUGS}
        missing = CORE_SLUGS.difference(production_pages)
        if missing:
            raise CheckFailed(f"Production is missing core pages: {', '.join(sorted(missing))}")
        headers = admin_headers(client)
        local = require_response(client.get(f"{args.target.rstrip('/')}/api/admin/pages", headers=headers), "local pages").json()
        by_slug = {page["slug"]: page for page in local}
        for slug in sorted(CORE_SLUGS):
            page = production_pages[slug]
            payload = {"slug": slug, "title": page["title"], "content": page["content"], "is_published": bool(page.get("is_published", True))}
            existing = by_slug.get(slug)
            url = f"{args.target.rstrip('/')}/api/admin/pages"
            method = "POST"
            if existing:
                url += f"/{existing['id']}"
                method = "PUT"
            require_response(client.request(method, url, headers=headers, json=payload), f"sync {slug}")
    return "production About, Contact, Privacy, and Disclaimer content copied to local"


if __name__ == "__main__":
    raise SystemExit(run(check))
