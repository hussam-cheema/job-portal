"""Monthly national editions. Edition dates are NOT annual observation dates."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import Job, MarketReport, TaxonomyTerm
from app.constants import PAKISTAN_PROVINCE_BY_CITY
from app.services.employment_breakdowns import national_breakdowns, new_breakdown, occupation_group, listing_provinces, serialize_breakdown
from app.utils import normalize_job_type

PKT = ZoneInfo("Asia/Karachi")
# Official World Development Indicators, source 2: national ILO modelled rates.
INDICATORS = {
    "unemployment": "SL.UEM.TOTL.ZS",
    "youth_unemployment": "SL.UEM.1524.ZS",
    "female_unemployment": "SL.UEM.TOTL.FE.ZS",
    "male_unemployment": "SL.UEM.TOTL.MA.ZS",
    "participation": "SL.TLF.CACT.ZS",
    "female_participation": "SL.TLF.CACT.FE.ZS",
    "male_participation": "SL.TLF.CACT.MA.ZS",
    "employment_ratio": "SL.EMP.TOTL.SP.ZS",
    "agriculture": "SL.AGR.EMPL.ZS",
    "industry": "SL.IND.EMPL.ZS",
    "services": "SL.SRV.EMPL.ZS",
    "wage_employment": "SL.EMP.WORK.ZS",
    "vulnerable_employment": "SL.EMP.VULN.ZS",
    "self_employment": "SL.EMP.SELF.ZS",
}
API_URL = "https://api.worldbank.org/v2/country/PAK/indicator/" + ";".join(
    INDICATORS.values()
)


def month_date(value: str) -> date:
    if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value):
        raise ValueError("Use a month in YYYY-MM format")
    return date.fromisoformat(value + "-01")


def parse_observations(rows: list[dict]) -> dict:
    series = {}
    for key, code in INDICATORS.items():
        values = {}
        title = None
        for row in rows:
            if (
                row.get("countryiso3code") != "PAK"
                or row.get("indicator", {}).get("id") != code
            ):
                continue
            title = row["indicator"]["value"]
            if row.get("value") is None:
                continue
            year, value = str(row.get("date", "")), row["value"]
            if (
                not re.fullmatch(r"\d{4}", year)
                or isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= 100
            ):
                raise ValueError(f"Invalid official observation for {code}")
            if year in values and values[year] != value:
                raise ValueError(f"Conflicting observations for {code}/{year}")
            values[year] = value
        if not values:
            raise ValueError(f"Official data missing for {code}; publication deferred")
        points = [
            {"year": year, "value": value} for year, value in sorted(values.items())
        ]
        series[key] = {
            "code": code,
            "title": title,
            "unit": "%",
            "points": points,
            "latest": points[-1],
            "source_url": f"https://data.worldbank.org/indicator/{code}?locations=PK",
            "api_url": f"https://api.worldbank.org/v2/country/PAK/indicator/{code}?format=json&source=2&per_page=2000",
        }
    return series


def fetch_national_data() -> dict:
    """Fixed official host, finite timeouts, complete pagination, fail closed."""
    rows, updates = [], set()
    with httpx.Client(
        timeout=30,
        transport=httpx.HTTPTransport(retries=2),
        follow_redirects=False,
        headers={
            "User-Agent": "PakistanJobsMarket/1.0 (national-statistics-dashboard)"
        },
    ) as client:
        page = 1
        while True:
            response = client.get(
                API_URL,
                params={
                    "format": "json",
                    "source": 2,
                    "per_page": 2000,
                    "date": f"2000:{datetime.now(timezone.utc).year}",
                    "page": page,
                },
            )
            response.raise_for_status()
            payload = response.json()
            if (
                not isinstance(payload, list)
                or len(payload) != 2
                or not isinstance(payload[1], list)
            ):
                raise ValueError("Unexpected World Bank response; publication deferred")
            meta, items = payload
            pages = int(meta.get("pages", 0))
            # The official multi-indicator endpoint returns sourceid=null even
            # for an explicit source=2 query. Rows still require exact codes/PAK.
            if (
                meta.get("sourceid") not in (None, "2", 2)
                or int(meta.get("page", 0)) != page
                or not 1 <= pages <= 20
            ):
                raise ValueError(
                    "Invalid World Bank pagination/source; publication deferred"
                )
            rows.extend(items)
            updates.add(meta.get("lastupdated", ""))
            if page >= pages:
                if len(rows) != int(meta["total"]):
                    raise ValueError(
                        "Incomplete World Bank response; publication deferred"
                    )
                break
            page += 1
    series = parse_observations(rows)
    breakdowns = national_breakdowns()
    return {
        "series": series,
        "breakdowns": breakdowns,
        "source_updated": sorted(updates),
        "data_fingerprint": hashlib.sha256(
            json.dumps({"series": series, "breakdowns": breakdowns}, sort_keys=True).encode()
        ).hexdigest(),
        "provider": "World Bank World Development Indicators / ILO modelled estimates",
        "license_url": "https://datacatalog.worldbank.org/public-licenses#cc-by",
    }


def current_site_statistics(db: Session) -> dict:
    """Current inventory, grouped by the advertisement publication date.

    These are date-only publication values, not UTC event timestamps. Count each
    job once, including expired listings, and keep undated records in totals.
    """
    captured = datetime.now(timezone.utc)
    current_month = captured.astimezone(PKT).strftime("%Y-%m")
    rows = db.execute(
        select(
            Job.published_date, Job.job_type, Job.tags, Job.cities, Job.provinces,
        )
    ).all()

    def empty():
        return {"total": 0, "government": 0, "private": 0, "unspecified": 0}

    overall, undated = empty(), empty()
    months = {current_month: empty()}
    for published, sector, _tags, _cities, _provinces in rows:
        normalized = normalize_job_type(sector)
        key = normalized if normalized in ("government", "private") else "unspecified"
        bucket = (
            months.setdefault(published.strftime("%Y-%m"), empty())
            if published
            else undated
        )
        for target in (overall, bucket):
            target["total"] += 1
            target[key] += 1
    province_by_city = {name.casefold(): province for name, province in db.execute(
        select(TaxonomyTerm.name, TaxonomyTerm.province).where(TaxonomyTerm.kind == "city")
    ).all() if province}
    province_by_city.update({name.casefold(): province for name, province in PAKISTAN_PROVINCE_BY_CITY.items()})
    all_breakdowns = new_breakdown()
    monthly_breakdowns = {month: new_breakdown() for month in months}
    for published, _sector, tags, cities, provinces in rows:
        targets = [all_breakdowns]
        if published:
            targets.append(monthly_breakdowns.setdefault(published.strftime("%Y-%m"), new_breakdown()))
        occupation = occupation_group(tags)
        locations = listing_provinces(cities, provinces, province_by_city)
        for target in targets:
            target["occupations"][occupation] += 1
            target["provinces"].update(locations)
    return {
        "collected_at": captured.isoformat().replace("+00:00", "Z"),
        "current_month": current_month,
        "overall": overall,
        "undated": undated,
        "breakdowns": {
            "overall": serialize_breakdown(all_breakdowns),
            "months": {month: serialize_breakdown(value) for month, value in monthly_breakdowns.items()},
        },
        "months": [
            {"month": month, **counts}
            for month, counts in sorted(months.items(), reverse=True)
        ],
    }


def site_supplement(db: Session, edition: date) -> dict:
    end = datetime.combine(edition, datetime.min.time())
    last = date.fromordinal(edition.toordinal() - 1)
    start = datetime(last.year, last.month, 1)
    rows = db.execute(
        select(Job.job_type, func.count(Job.id))
        .where(Job.published_date >= start, Job.published_date < end)
        .group_by(Job.job_type)
    ).all()
    counts = {"government": 0, "private": 0, "unspecified": 0}
    for sector, count in rows:
        normalized = normalize_job_type(sector)
        counts[normalized if normalized in counts else "unspecified"] += count
    return {
        "month": start.strftime("%Y-%m"),
        "total": sum(counts.values()),
        **counts,
        "source_url": "/",
        "scope": "Based on current website records only; advertisements, not vacancies or national hiring totals.",
    }


def publish_due_reports(db: Session, *, now: datetime | None = None) -> list[str]:
    """Publish the current edition once on/after the 1st in Pakistan.

    The production 15-minute cron and API fallback both call this. Transaction
    locking plus a month primary key prevent duplicates. Past editions remain
    immutable; missed months are not invented using later official revisions.
    """
    captured = now or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    edition = captured.astimezone(PKT).date().replace(day=1)
    month = edition.strftime("%Y-%m")
    if db.get_bind().dialect.name == "postgresql":
        if not db.execute(text("SELECT pg_try_advisory_xact_lock(714209031)")).scalar():
            return []
    if db.get(MarketReport, month):
        return []
    national = fetch_national_data()
    previous = db.scalar(
        select(MarketReport)
        .where(MarketReport.month < month)
        .order_by(MarketReport.month.desc())
        .limit(1)
    )
    data = {
        "schema_version": 1,
        "month": month,
        "published_at": captured.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "national": national,
        "national_data_changed": (
            national["data_fingerprint"]
            != previous.data["national"]["data_fingerprint"]
        )
        if previous
        else None,
        "site_supplement": site_supplement(db, edition),
    }
    db.add(
        MarketReport(
            month=month,
            data=data,
            published_at=captured.astimezone(timezone.utc).replace(tzinfo=None),
        )
    )
    db.commit()
    return [month]


def report_summary(data: dict) -> dict:
    return {
        "month": data["month"],
        "published_at": data["published_at"],
        "unemployment": data["national"]["series"]["unemployment"]["latest"],
    }
