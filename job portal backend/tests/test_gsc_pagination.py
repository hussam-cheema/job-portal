import os
from datetime import date

os.environ.setdefault("JOBPORTAL_TESTING", "true")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.services.seo_tools import (
    GSC_SEARCH_ANALYTICS_PAGE_SIZE,
    _count_unique_gsc_queries,
    _fetch_gsc_search_analytics_rows,
)


class _Request:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class _SearchAnalytics:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def query(self, *, siteUrl, body):
        self.calls.append({"siteUrl": siteUrl, "body": body})
        return _Request({"rows": self.pages.get(body["startRow"], [])})


class _Service:
    def __init__(self, pages):
        self.endpoint = _SearchAnalytics(pages)

    def searchanalytics(self):
        return self.endpoint


def test_gsc_search_analytics_fetches_every_offset_page():
    rows = [
        {"keys": [f"query-{index}", f"https://example.com/{index}"]}
        for index in range(5)
    ]
    service = _Service({0: rows[:2], 2: rows[2:4], 4: rows[4:]})

    result = _fetch_gsc_search_analytics_rows(
        service,
        site="sc-domain:example.com",
        start=date(2026, 8, 1),
        end=date(2026, 8, 28),
        page_size=2,
    )

    assert result == rows
    assert [call["body"]["startRow"] for call in service.endpoint.calls] == [0, 2, 4]
    assert all(call["body"]["rowLimit"] == 2 for call in service.endpoint.calls)
    assert all(call["body"]["dimensions"] == ["query", "page"] for call in service.endpoint.calls)


def test_gsc_page_size_is_capped_at_google_maximum():
    service = _Service({0: []})

    _fetch_gsc_search_analytics_rows(
        service,
        site="sc-domain:example.com",
        start=date(2026, 8, 1),
        end=date(2026, 8, 28),
        page_size=GSC_SEARCH_ANALYTICS_PAGE_SIZE + 1,
    )

    assert service.endpoint.calls[0]["body"]["rowLimit"] == 25_000


def test_unique_gsc_query_count_is_not_limited_to_one_thousand():
    rows = [
        {"keyword": f"Query {index}", "url": f"https://example.com/{index}"}
        for index in range(1_005)
    ]
    rows.append({"keyword": "  QUERY 0  ", "url": "https://example.com/duplicate"})

    assert _count_unique_gsc_queries(rows) == 1_005
