import copy
import os
from datetime import datetime, timezone

os.environ.setdefault("JOBPORTAL_TESTING", "true")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Job, MarketReport
from app.routers.market_reports import router
from app.services import market_reports as service
from app.services.employment_breakdowns import national_breakdowns, listing_provinces


def official_rows():
    return [
        {
            "countryiso3code": "PAK",
            "indicator": {"id": code, "value": key},
            "date": year,
            "value": value,
        }
        for key, code in service.INDICATORS.items()
        for year, value in [("2023", 0), ("2024", 5.5), ("2025", None)]
    ]


def test_verified_pbs_breakdowns_preserve_report_values_and_rounding():
    data = national_breakdowns()
    assert data["period"] == "2024-25"
    assert len(data["occupations"]["items"]) == 9
    assert sum(row["value"] for row in data["occupations"]["items"]) == pytest.approx(100.1)
    assert data["provinces"]["pakistan_total"] == 77.2
    assert {row["name"]: row["value"] for row in data["provinces"]["items"]} == {
        "Punjab": 44.7, "Sindh": 17.5, "Khyber Pakhtunkhwa": 11.3, "Balochistan": 3.8,
    }
    data["provinces"]["items"][0]["value"] = 0
    assert national_breakdowns()["provinces"]["items"][0]["value"] == 44.7


def test_website_breakdowns_use_publication_month_unique_tags_and_actual_provinces(db):
    cases = [
        ("2026-08-01", ["Software Engineering", "software engineering"], ["Karachi"], ["Punjab"]),
        ("2026-08-15", ["Government"], ["Pakistan"], ["Punjab", "Sindh"]),
        ("2026-09-01", ["Teachers", "Drivers"], ["Lahore", "Karachi", "Karachi"], []),
        ("2026-09-02", [], [], []),
    ]
    for i, (published, tags, cities, provinces) in enumerate(cases):
        db.add(Job(id=str(i), slug=str(i), title="Advertisement", description="Test",
                   published_date=datetime.fromisoformat(published), tags=tags, cities=cities, provinces=provinces))
    db.commit()
    data = service.current_site_statistics(db)
    overall = data["breakdowns"]["overall"]
    assert sum(item["value"] for item in overall["occupations"]) == data["overall"]["total"] == 4
    assert {item["name"]: item["value"] for item in overall["occupations"]} == {"Professionals": 1, "Unclassified": 2, "Multiple occupation groups": 1}
    assert {item["name"]: item["value"] for item in overall["provinces"]} == {"Sindh": 2, "Punjab": 1, "Pakistan / nationwide": 1, "Location unspecified": 1}
    august = data["breakdowns"]["months"]["2026-08"]
    assert sum(item["value"] for item in august["occupations"]) == 2
    assert "Punjab" not in {item["name"] for item in august["provinces"]}
    assert listing_provinces([], ["punjab", "Punjab"], {}) == ["Punjab"]


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def national(monkeypatch):
    data = {
        "series": service.parse_observations(official_rows()),
        "data_fingerprint": "v1",
        "source_updated": ["2026-07-13"],
        "provider": "World Bank / ILO",
        "license_url": "https://datacatalog.worldbank.org/public-licenses#cc-by",
    }
    monkeypatch.setattr(service, "fetch_national_data", lambda: copy.deepcopy(data))
    return data


def test_parser_preserves_zero_skips_null_sorts_and_ignores_other_countries():
    rows = official_rows() + [
        {
            "countryiso3code": "IND",
            "indicator": {"id": "SL.UEM.TOTL.ZS", "value": "wrong"},
            "date": "2026",
            "value": 99,
        }
    ]
    series = service.parse_observations(rows)
    assert len(series) == 14
    assert series["unemployment"]["latest"] == {"year": "2024", "value": 5.5}
    assert series["unemployment"]["points"][0]["value"] == 0
    assert "locations=PK" in series["unemployment"]["source_url"]


@pytest.mark.parametrize("bad", [-1, 101, float("nan"), float("inf"), "5.5", True])
def test_bad_values_cannot_publish(bad):
    rows = official_rows()
    rows[0]["value"] = bad
    with pytest.raises(ValueError):
        service.parse_observations(rows)


def test_missing_indicator_cannot_silently_become_zero():
    with pytest.raises(ValueError, match="missing"):
        service.parse_observations(official_rows()[3:])


def test_pakistan_month_rollover_immutable_editions_and_no_invented_archives(
    db, national
):
    before = datetime(2026, 8, 31, 18, 59, tzinfo=timezone.utc)
    after = datetime(2026, 8, 31, 19, 0, tzinfo=timezone.utc)
    assert service.publish_due_reports(db, now=before) == ["2026-08"]
    snapshot = copy.deepcopy(db.get(MarketReport, "2026-08").data)
    national["data_fingerprint"] = "v2"
    national["series"]["unemployment"]["latest"]["value"] = 7
    assert service.publish_due_reports(db, now=before) == []
    assert service.publish_due_reports(db, now=after) == ["2026-09"]
    assert db.get(MarketReport, "2026-08").data == snapshot
    assert db.get(MarketReport, "2026-09").data["national_data_changed"] is True
    assert service.publish_due_reports(
        db, now=datetime(2026, 11, 1, tzinfo=timezone.utc)
    ) == ["2026-11"]
    assert db.get(MarketReport, "2026-10") is None
    assert db.get(MarketReport, "2026-11").data["national_data_changed"] is False


def test_site_supplement_is_separate_previous_calendar_month(db, national):
    for i, (when, sector) in enumerate(
        [
            ("2026-08-01", "govt"),
            ("2026-08-31", "private"),
            ("2026-08-15", None),
            ("2026-09-01", "private"),
        ]
    ):
        db.add(
            Job(
                id=str(i),
                slug=str(i),
                title="Example job",
                description="Test",
                published_date=datetime.fromisoformat(when),
                job_type=sector,
            )
        )
    db.commit()
    service.publish_due_reports(db, now=datetime(2026, 9, 6, tzinfo=timezone.utc))
    report = db.get(MarketReport, "2026-09").data
    assert report["site_supplement"]["total"] == 3
    assert report["site_supplement"]["government"] == 1
    assert report["site_supplement"]["unspecified"] == 1
    current = service.current_site_statistics(db)
    assert current["overall"] == {
        "total": 4,
        "government": 1,
        "private": 2,
        "unspecified": 1,
    }
    months = {row["month"]: row for row in current["months"]}
    assert months["2026-08"]["total"] == 3
    assert months["2026-09"]["total"] == 1
    assert (
        sum(row["total"] for row in current["months"]) + current["undated"]["total"]
        == current["overall"]["total"]
    )
    db.add(
        Job(
            id="new",
            slug="new",
            title="New",
            description="Test",
            published_date=datetime(2026, 9, 8),
            job_type="government",
        )
    )
    db.commit()
    assert service.current_site_statistics(db)["overall"]["total"] == 5
    assert db.get(MarketReport, "2026-09").data["site_supplement"]["total"] == 3
    assert report["national"]["series"]["unemployment"]["latest"]["value"] == 5.5


def test_provider_failure_leaves_database_unchanged_and_can_retry(
    db, monkeypatch, national
):
    def fail():
        raise httpx.ReadTimeout("Provider temporarily unavailable")

    monkeypatch.setattr(service, "fetch_national_data", fail)
    with pytest.raises(httpx.ReadTimeout):
        service.publish_due_reports(db)
    db.rollback()
    assert db.scalars(select(MarketReport)).all() == []
    monkeypatch.setattr(service, "fetch_national_data", lambda: national)
    assert len(service.publish_due_reports(db)) == 1


def test_public_json_routes_and_invalid_months_are_read_only(db, national):
    service.publish_due_reports(db, now=datetime(2026, 9, 6, tzinfo=timezone.utc))
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        listing = client.get("/api/market-reports")
        assert listing.status_code == 200
        assert listing.json()["reports"][0]["month"] == "2026-09"
        response = client.get("/api/market-reports/2026-09")
        assert (
            response.json()["national"]["series"]["unemployment"]["latest"]["year"]
            == "2024"
        )
        assert response.headers["content-type"] == "application/json"
        stats = client.get("/api/market-reports/site-statistics")
        assert stats.status_code == 200
        assert stats.headers["content-type"] == "application/json"
        assert stats.json()["overall"]["total"] == 0
        assert stats.json()["months"][0]["month"] == stats.json()["current_month"]
        assert stats.json()["months"][0]["total"] == 0
        assert stats.json()["breakdowns"]["overall"] == {"occupations": [], "provinces": []}
        breakdowns = client.get("/api/market-reports/national-breakdowns")
        assert breakdowns.status_code == 200
        assert breakdowns.json()["provinces"]["pakistan_total"] == 77.2
        assert "max-age=300" in breakdowns.headers["cache-control"]
        assert client.post("/api/market-reports/site-statistics").status_code == 405
        for month in ["2026-08", "2026-13", "0000-01", "2026-09' OR '1'='1", "latest"]:
            assert client.get(f"/api/market-reports/{month}").status_code == 404
        assert client.post("/api/market-reports/2026-09").status_code == 405
    assert len(db.scalars(select(MarketReport)).all()) == 1


def test_cron_publishes_even_if_newsletter_delivery_fails(monkeypatch):
    from app.commands import newsletter_retry, market_reports

    called = []
    monkeypatch.setattr(newsletter_retry, "setup_logging", lambda: None)
    monkeypatch.setattr(market_reports, "run", lambda: called.append("reports"))

    def fail():
        raise RuntimeError("Mail unavailable")

    monkeypatch.setattr(newsletter_retry, "run", fail)
    with pytest.raises(RuntimeError):
        newsletter_retry.main()
    assert called == ["reports"]


def test_fetch_validates_pagination_and_official_host(monkeypatch):
    rows = official_rows()
    calls = []

    def handle(request):
        assert request.url.host == "api.worldbank.org"
        assert request.url.params["source"] == "2"
        page = int(request.url.params["page"])
        calls.append(page)
        items = rows[:20] if page == 1 else rows[20:]
        return httpx.Response(
            200,
            json=[
                {
                    "page": page,
                    "pages": 2,
                    "sourceid": None,
                    "total": len(rows),
                    "lastupdated": "2026-07-13",
                },
                items,
            ],
        )

    monkeypatch.setattr(
        service.httpx, "HTTPTransport", lambda **kwargs: httpx.MockTransport(handle)
    )
    result = service.fetch_national_data()
    assert calls == [1, 2]
    assert len(result["series"]) == 14
