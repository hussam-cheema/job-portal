from __future__ import annotations

DIRECT_PAGE_SLUGS = {
    "about",
    "contact",
    "privacy",
    "disclaimer",
    "jobs-by-cities",
    "jobs-by-provinces",
    "jobs-by-categories",
    "jobs-by-organizations",
    "jobs-by-newspapers",
}

DIRECTORY_PAGE_PATHS = {
    "city": "/locations",
    "province": "/locations",
    "category": "/categories",
    "organization": "/companies",
    "newspaper": "/newspapers",
}

VALID_PAGE_TYPES = {"standard", *DIRECTORY_PAGE_PATHS}


def page_slug_namespace(page_type: str) -> str:
    """Return the public route namespace that owns a Page slug."""
    return "location" if page_type in {"city", "province"} else page_type


def public_page_path(page_type: str, slug: str) -> str:
    if page_type in DIRECTORY_PAGE_PATHS:
        return f"{DIRECTORY_PAGE_PATHS[page_type]}/{slug}"
    if slug in DIRECT_PAGE_SLUGS:
        return f"/{slug}"
    return f"/p/{slug}"
