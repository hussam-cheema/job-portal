from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
import threading
import time
from collections import OrderedDict
from calendar import monthrange
from datetime import datetime, timedelta
from urllib.parse import quote, unquote
from uuid import uuid4

import httpx
import pycountry
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.config import cfg, jwt_secret
from app.database import get_db
from app.logging_config import get_logger
from app.models import AnalyticsVisit, User
from app.schemas import AnalyticsDashboard, AnalyticsRealtime, AnalyticsVisitIn

router = APIRouter()
logger = get_logger("jobportal.analytics")
BOT_PATTERN = re.compile(r"bot|crawler|spider|slurp|preview|headless", re.I)
INVALID_COUNTRY_CODES = {"", "XX", "ZZ", "T1", "UNKNOWN"}
COUNTRY_ALIASES = {
    "EL": "Greece",
    "UK": "United Kingdom",
    "XK": "Kosovo",
}
_LOCATION_CACHE_MAX = 2048
_LOCATION_CACHE: OrderedDict[
    str,
    tuple[float, tuple[str, str | None, str | None]],
] = OrderedDict()
_LOCATION_CACHE_LOCK = threading.Lock()


def _enabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _clean_country(value: str | None) -> str | None:
    country = unquote(value or "").strip().strip('"')
    upper = country.upper()
    if upper in INVALID_COUNTRY_CODES:
        return None
    if upper in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[upper]
    try:
        match = (
            pycountry.countries.get(alpha_2=upper)
            if len(upper) == 2 and upper.isalpha()
            else pycountry.countries.lookup(country)
        )
    except LookupError:
        match = None
    if match is not None:
        return str(getattr(match, "common_name", match.name))[:100]
    # Preserve an already human-readable provider value, but never leak an
    # unresolved two/three-letter code into the dashboard.
    if len(country) <= 3 and country.isalpha():
        return None
    return country[:100] or None


def _clean_location_name(value: str | None, limit: int = 150) -> str | None:
    clean = re.sub(r"\s+", " ", unquote(value or "").strip().strip('"'))
    if clean.casefold() in {"", "unknown", "n/a", "none", "null"}:
        return None
    if clean.islower():
        clean = clean.title()
    return clean[:limit] or None


def _global_ip(value: str | None) -> str | None:
    raw = (value or "").strip().strip('"')
    if not raw:
        return None
    if raw.lower().startswith("for="):
        raw = raw[4:].strip().strip('"')
    if raw.startswith("[") and "]" in raw:
        raw = raw[1 : raw.index("]")]
    elif raw.count(":") == 1 and "." in raw:
        raw = raw.rsplit(":", 1)[0]
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return None
    return str(address) if address.is_global else None


def _client_ip(request: Request) -> str | None:
    trust_proxy = _enabled(cfg("analytics", "trust_proxy_headers", default=True))
    candidates: list[str | None] = []
    if trust_proxy:
        candidates.extend(
            [
                request.headers.get("cf-connecting-ip"),
                request.headers.get("true-client-ip"),
                # Railway documents X-Real-IP as the original client address.
                request.headers.get("x-real-ip"),
            ]
        )
        candidates.extend((request.headers.get("x-forwarded-for") or "").split(","))
        forwarded = request.headers.get("forwarded") or ""
        candidates.extend(
            part.strip()
            for entry in forwarded.split(",")
            for part in entry.split(";")
            if part.strip().lower().startswith("for=")
        )
    candidates.append(request.client.host if request.client else None)
    for candidate in candidates:
        if address := _global_ip(candidate):
            return address
    return None


def _lookup_public_ip(ip: str) -> tuple[str | None, str | None, str | None]:
    if not _enabled(cfg("analytics", "geolocation_enabled", default=True)):
        return None, None, None
    now = time.monotonic()
    with _LOCATION_CACHE_LOCK:
        cached = _LOCATION_CACHE.get(ip)
        if cached and cached[0] > now:
            _LOCATION_CACHE.move_to_end(ip)
            return cached[1]
        if cached:
            _LOCATION_CACHE.pop(ip, None)

    primary = str(
        cfg("analytics", "geolocation_url", default="https://ipwho.is/{ip}")
        or "https://ipwho.is/{ip}"
    )
    fallback = str(
        cfg("analytics", "geolocation_fallback_url", default="") or ""
    ).strip()
    templates = list(dict.fromkeys(value for value in (primary, fallback) if value))
    timeout = float(cfg("analytics", "geolocation_timeout_seconds", default=4) or 4)
    for template in templates:
        try:
            response = httpx.get(
                template.format(ip=quote(ip, safe="")), timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            if (
                not isinstance(data, dict)
                or data.get("success") is False
                or data.get("error") is True
            ):
                continue
            country = _clean_country(
                data.get("country_code")
                or data.get("country")
                or data.get("country_name")
            )
            if not country:
                continue
            resolved = (
                country,
                _clean_location_name(data.get("region") or data.get("regionName")),
                _clean_location_name(data.get("city")),
            )
            ttl = max(
                60.0,
                float(
                    cfg("analytics", "geolocation_cache_seconds", default=86400)
                    or 86400
                ),
            )
            with _LOCATION_CACHE_LOCK:
                _LOCATION_CACHE[ip] = (now + ttl, resolved)
                _LOCATION_CACHE.move_to_end(ip)
                while len(_LOCATION_CACHE) > _LOCATION_CACHE_MAX:
                    _LOCATION_CACHE.popitem(last=False)
            return resolved
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            logger.debug("analytics_geolocation_provider_failed provider=%s", template)
    # Do not cache failures: a transient provider outage must be retried by the
    # next heartbeat instead of making this visitor Unknown for the process life.
    return None, None, None


def _clear_location_cache() -> None:
    """Test/operations helper for immediately discarding cached successful lookups."""
    with _LOCATION_CACHE_LOCK:
        _LOCATION_CACHE.clear()


def _location(request: Request) -> tuple[str, str | None, str | None, bool]:
    trust_proxy = _enabled(cfg("analytics", "trust_proxy_headers", default=True))
    if trust_proxy:
        country = _clean_country(
            request.headers.get("cf-ipcountry")
            or request.headers.get("x-vercel-ip-country")
            or request.headers.get("cloudfront-viewer-country")
            or request.headers.get("x-country-code")
        )
        if country:
            region = _clean_location_name(
                request.headers.get("cf-region")
                or request.headers.get("x-vercel-ip-country-region")
                or request.headers.get("x-region")
            )
            city = _clean_location_name(
                request.headers.get("cf-ipcity")
                or request.headers.get("x-vercel-ip-city")
                or request.headers.get("x-city")
            )
            return country, region, city, True

    ip = _client_ip(request)
    country, region, city = _lookup_public_ip(ip) if ip else (None, None, None)
    return country or "Unknown", region, city, bool(country)


def _latest_verified_location(
    db: Session,
    visitor_hash: str,
) -> tuple[str, str | None, str | None] | None:
    row = db.execute(
        select(AnalyticsVisit.country, AnalyticsVisit.region, AnalyticsVisit.city)
        .where(
            AnalyticsVisit.visitor_hash == visitor_hash,
            AnalyticsVisit.location_verified.is_(True),
        )
        .order_by(AnalyticsVisit.visited_at.desc())
        .limit(1)
    ).first()
    if not row or not _clean_country(row.country):
        return None
    return (
        _clean_country(row.country) or "Unknown",
        _clean_location_name(row.region),
        _clean_location_name(row.city),
    )


def _verified_locations_by_visitor(
    db: Session,
    visitor_hashes: set[str],
) -> dict[str, tuple[str, str | None, str | None]]:
    """Resolve legacy Unknown rows from a later verified visit by the same browser."""
    resolved: dict[str, tuple[str, str | None, str | None]] = {}
    hashes = list(visitor_hashes)
    for start in range(0, len(hashes), 500):
        rows = db.execute(
            select(
                AnalyticsVisit.visitor_hash,
                AnalyticsVisit.country,
                AnalyticsVisit.region,
                AnalyticsVisit.city,
            )
            .where(
                AnalyticsVisit.visitor_hash.in_(hashes[start : start + 500]),
                AnalyticsVisit.location_verified.is_(True),
            )
            .order_by(AnalyticsVisit.visited_at.desc())
        ).all()
        for row in rows:
            country = _clean_country(row.country)
            if row.visitor_hash not in resolved and country:
                resolved[row.visitor_hash] = (
                    country,
                    _clean_location_name(row.region),
                    _clean_location_name(row.city),
                )
    return resolved


def _effective_row_location(
    row: AnalyticsVisit,
    verified: dict[str, tuple[str, str | None, str | None]],
) -> tuple[str, str | None, str | None]:
    country = _clean_country(row.country)
    if row.location_verified and country:
        return (
            country,
            _clean_location_name(row.region),
            _clean_location_name(row.city),
        )
    return verified.get(row.visitor_hash, ("Unknown", None, None))


def _location_identity(
    location: tuple[str, str | None, str | None],
) -> tuple[str, str | None, str | None]:
    """Use case-insensitive location identity while preserving display spelling."""
    country, region, city = location
    return (
        country.casefold(),
        region.casefold() if region else None,
        city.casefold() if city else None,
    )


@router.post("/analytics/visit", status_code=201)
def record_visit(
    payload: AnalyticsVisitIn, request: Request, db: Session = Depends(get_db)
):
    if BOT_PATTERN.search(request.headers.get("user-agent") or ""):
        return {"ok": True}
    visitor_hash = hmac.new(
        jwt_secret().encode(), payload.visitor_id.encode(), hashlib.sha256
    ).hexdigest()
    path = "/" + payload.path.lstrip("/").split("?", 1)[0][:499]
    cutoff = datetime.utcnow() - timedelta(minutes=30)
    duplicate = db.execute(
        select(AnalyticsVisit).where(
            AnalyticsVisit.visitor_hash == visitor_hash,
            AnalyticsVisit.path == path,
            AnalyticsVisit.visited_at >= cutoff,
        )
    ).scalar_one_or_none()
    if duplicate:
        # Heartbeats refresh presence without increasing monthly page-view totals.
        duplicate.visited_at = datetime.utcnow()
        if not duplicate.location_verified or not duplicate.city:
            country, region, city, location_verified = _location(request)
            if not location_verified:
                previous = _latest_verified_location(db, visitor_hash)
                if previous:
                    country, region, city = previous
                    location_verified = True
            if location_verified:
                duplicate.country = country
                if region:
                    duplicate.region = region
                if city:
                    duplicate.city = city
                duplicate.location_verified = True
        db.commit()
    else:
        country, region, city, location_verified = _location(request)
        if not location_verified:
            previous = _latest_verified_location(db, visitor_hash)
            if previous:
                country, region, city = previous
                location_verified = True
        db.add(
            AnalyticsVisit(
                id=str(uuid4()),
                visitor_hash=visitor_hash,
                path=path,
                country=country,
                region=region,
                city=city,
                location_verified=location_verified,
                visited_at=datetime.utcnow(),
            )
        )
        db.commit()
    return {"ok": True}


@router.get("/admin/analytics/realtime", response_model=AnalyticsRealtime)
def realtime_analytics(
    window_minutes: int = Query(5, ge=1, le=60),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=window_minutes)
    rows = db.execute(
        select(
            AnalyticsVisit.visitor_hash,
            AnalyticsVisit.path,
            AnalyticsVisit.country,
            AnalyticsVisit.region,
            AnalyticsVisit.city,
            AnalyticsVisit.location_verified,
            AnalyticsVisit.visited_at,
        )
        .where(AnalyticsVisit.visited_at >= cutoff)
        .order_by(AnalyticsVisit.visited_at.desc())
    ).all()

    active_visitors = {row.visitor_hash for row in rows}
    verified_locations = _verified_locations_by_visitor(
        db,
        {
            row.visitor_hash
            for row in rows
            if not row.location_verified or not _clean_country(row.country)
        },
    )
    pages: dict[str, dict[str, object]] = {}
    locations: dict[tuple[str, str | None, str | None], dict[str, object]] = {}
    for row in rows:
        page = pages.setdefault(
            row.path,
            {"visitors": set(), "page_views": 0, "last_seen": row.visited_at},
        )
        page["visitors"].add(row.visitor_hash)  # type: ignore[union-attr]
        page["page_views"] = int(page["page_views"]) + 1
        if row.visited_at > page["last_seen"]:  # type: ignore[operator]
            page["last_seen"] = row.visited_at
        display_location = _effective_row_location(row, verified_locations)
        location_key = _location_identity(display_location)
        location = locations.setdefault(
            location_key,
            {
                "country": display_location[0],
                "region": display_location[1],
                "city": display_location[2],
                "visitors": set(),
                "last_seen": row.visited_at,
            },
        )
        location["visitors"].add(row.visitor_hash)  # type: ignore[union-attr]
        if row.visited_at > location["last_seen"]:  # type: ignore[operator]
            location["last_seen"] = row.visited_at

    page_rows = [
        {
            "path": path,
            "visitors": len(data["visitors"]),
            "page_views": data["page_views"],
            "last_seen": data["last_seen"],
        }
        for path, data in pages.items()
    ]
    page_rows.sort(key=lambda item: item["last_seen"], reverse=True)
    location_rows = [
        {
            "country": data["country"],
            "region": data["region"],
            "city": data["city"],
            "visitors": len(data["visitors"]),
            "last_seen": data["last_seen"],
        }
        for data in locations.values()
    ]
    location_rows.sort(key=lambda item: item["last_seen"], reverse=True)
    return AnalyticsRealtime(
        window_minutes=window_minutes,
        active_visitors=len(active_visitors),
        page_views=len(rows),
        pages=page_rows,
        locations=location_rows,
        generated_at=now,
    )


def _month_bounds(value: str | None) -> tuple[str, datetime, datetime]:
    try:
        start = (
            datetime.strptime(value, "%Y-%m")
            if value
            else datetime.utcnow().replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        )
    except ValueError:
        raise HTTPException(
            status_code=400, detail="month must use YYYY-MM format"
        ) from None
    start = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days = monthrange(start.year, start.month)[1]
    return start.strftime("%Y-%m"), start, start + timedelta(days=days)


@router.get("/admin/analytics", response_model=AnalyticsDashboard)
def analytics_dashboard(
    month: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    label, start, end = _month_bounds(month)
    rows = db.execute(
        select(
            AnalyticsVisit.visitor_hash,
            AnalyticsVisit.country,
            AnalyticsVisit.region,
            AnalyticsVisit.city,
            AnalyticsVisit.location_verified,
            AnalyticsVisit.visited_at,
        ).where(
            AnalyticsVisit.visited_at >= start,
            AnalyticsVisit.visited_at < end,
        )
    ).all()

    daily: dict[str, dict[str, set[str] | int]] = {}
    locations: dict[tuple[str, str | None, str | None], dict[str, object]] = {}
    all_visitors: set[str] = set()
    verified_locations = _verified_locations_by_visitor(
        db,
        {
            row.visitor_hash
            for row in rows
            if not row.location_verified or not _clean_country(row.country)
        },
    )
    for row in rows:
        all_visitors.add(row.visitor_hash)
        day = row.visited_at.strftime("%Y-%m-%d")
        day_data = daily.setdefault(day, {"visitors": set(), "page_views": 0})
        day_data["visitors"].add(row.visitor_hash)  # type: ignore[union-attr]
        day_data["page_views"] = int(day_data["page_views"]) + 1

        display_location = _effective_row_location(row, verified_locations)
        key = _location_identity(display_location)
        location = locations.setdefault(
            key,
            {
                "country": display_location[0],
                "region": display_location[1],
                "city": display_location[2],
                "visitors": set(),
                "page_views": 0,
            },
        )
        location["visitors"].add(row.visitor_hash)  # type: ignore[union-attr]
        location["page_views"] = int(location["page_views"]) + 1

    daily_points = [
        {
            "date": day,
            "visitors": len(data["visitors"]),
            "page_views": data["page_views"],
        }
        for day, data in sorted(daily.items())
    ]
    location_points = sorted(
        (
            {
                "country": data["country"],
                "region": data["region"],
                "city": data["city"],
                "visitors": len(data["visitors"]),
                "page_views": data["page_views"],
            }
            for data in locations.values()
        ),
        key=lambda item: int(item["visitors"]),
        reverse=True,
    )
    return AnalyticsDashboard(
        month=label,
        unique_visitors=len(all_visitors),
        page_views=len(rows),
        daily=daily_points,
        locations=location_points,
    )
