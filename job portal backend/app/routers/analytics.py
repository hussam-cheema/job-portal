from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
from calendar import monthrange
from datetime import datetime, timedelta
from functools import lru_cache
from urllib.parse import quote
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.config import cfg, jwt_secret
from app.database import get_db
from app.models import AnalyticsVisit, User
from app.schemas import AnalyticsDashboard, AnalyticsRealtime, AnalyticsVisitIn

router = APIRouter()
BOT_PATTERN = re.compile(r"bot|crawler|spider|slurp|preview|headless", re.I)
INVALID_COUNTRY_CODES = {"", "XX", "T1"}


def _enabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _clean_country(value: str | None) -> str | None:
    country = (value or "").strip()
    if country.upper() in INVALID_COUNTRY_CODES:
        return None
    return country[:100] or None


def _client_ip(request: Request) -> str | None:
    trust_proxy = _enabled(cfg("analytics", "trust_proxy_headers", default=True))
    candidates: list[str | None] = []
    if trust_proxy:
        candidates.extend(
            [
                request.headers.get("cf-connecting-ip"),
                (request.headers.get("x-forwarded-for") or "").split(",", 1)[0],
                request.headers.get("x-real-ip"),
            ]
        )
    candidates.append(request.client.host if request.client else None)
    for candidate in candidates:
        try:
            address = ipaddress.ip_address((candidate or "").strip())
            if address.is_global:
                return str(address)
        except ValueError:
            continue
    return None


@lru_cache(maxsize=2048)
def _lookup_public_ip(ip: str) -> tuple[str | None, str | None]:
    if not _enabled(cfg("analytics", "geolocation_enabled", default=True)):
        return None, None
    template = str(
        cfg("analytics", "geolocation_url", default="https://ipwho.is/{ip}")
        or "https://ipwho.is/{ip}"
    )
    timeout = float(cfg("analytics", "geolocation_timeout_seconds", default=4) or 4)
    try:
        response = httpx.get(template.format(ip=quote(ip, safe="")), timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if data.get("success") is False:
            return None, None
        country = _clean_country(data.get("country") or data.get("country_code"))
        region = str(data.get("region") or data.get("regionName") or "").strip()[:150] or None
        return country, region
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return None, None


def _location(request: Request) -> tuple[str, str | None, bool]:
    trust_proxy = _enabled(cfg("analytics", "trust_proxy_headers", default=True))
    if trust_proxy:
        country = _clean_country(
            request.headers.get("cf-ipcountry")
            or request.headers.get("x-vercel-ip-country")
            or request.headers.get("x-country-code")
        )
        if country:
            region = (
                request.headers.get("cf-region")
                or request.headers.get("x-vercel-ip-country-region")
                or request.headers.get("x-region")
            )
            return country, region[:150] if region else None, True

    ip = _client_ip(request)
    country, region = _lookup_public_ip(ip) if ip else (None, None)
    return country or "Unknown", region, bool(country)


@router.post("/analytics/visit", status_code=201)
def record_visit(payload: AnalyticsVisitIn, request: Request, db: Session = Depends(get_db)):
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
        db.commit()
    else:
        country, region, location_verified = _location(request)
        db.add(
            AnalyticsVisit(
                id=str(uuid4()),
                visitor_hash=visitor_hash,
                path=path,
                country=country,
                region=region,
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
        select(AnalyticsVisit)
        .where(AnalyticsVisit.visited_at >= cutoff)
        .order_by(AnalyticsVisit.visited_at.desc())
    ).scalars().all()

    active_visitors = {row.visitor_hash for row in rows}
    pages: dict[str, dict[str, object]] = {}
    for row in rows:
        page = pages.setdefault(
            row.path,
            {"visitors": set(), "page_views": 0, "last_seen": row.visited_at},
        )
        page["visitors"].add(row.visitor_hash)  # type: ignore[union-attr]
        page["page_views"] = int(page["page_views"]) + 1
        if row.visited_at > page["last_seen"]:  # type: ignore[operator]
            page["last_seen"] = row.visited_at

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
    return AnalyticsRealtime(
        window_minutes=window_minutes,
        active_visitors=len(active_visitors),
        page_views=len(rows),
        pages=page_rows,
        generated_at=now,
    )


def _month_bounds(value: str | None) -> tuple[str, datetime, datetime]:
    try:
        start = datetime.strptime(value, "%Y-%m") if value else datetime.utcnow().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="month must use YYYY-MM format") from None
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
        select(AnalyticsVisit).where(
            AnalyticsVisit.visited_at >= start,
            AnalyticsVisit.visited_at < end,
        )
    ).scalars().all()

    daily: dict[str, dict[str, set[str] | int]] = {}
    locations: dict[tuple[str, str | None], dict[str, set[str] | int]] = {}
    all_visitors: set[str] = set()
    for row in rows:
        all_visitors.add(row.visitor_hash)
        day = row.visited_at.strftime("%Y-%m-%d")
        day_data = daily.setdefault(day, {"visitors": set(), "page_views": 0})
        day_data["visitors"].add(row.visitor_hash)  # type: ignore[union-attr]
        day_data["page_views"] = int(day_data["page_views"]) + 1

        key = (
            (row.country or "Unknown") if row.location_verified else "Unknown",
            row.region if row.location_verified else None,
        )
        location = locations.setdefault(key, {"visitors": set(), "page_views": 0})
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
                "country": country,
                "region": region,
                "visitors": len(data["visitors"]),
                "page_views": data["page_views"],
            }
            for (country, region), data in locations.items()
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
