from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.r2_logging import R2ProductionLogHandler


PKT = ZoneInfo("Asia/Karachi")


class FakeR2Client:
    def __init__(self, initial_keys: list[str] | None = None):
        self.objects: dict[str, bytes] = {
            key: b"existing" for key in (initial_keys or [])
        }
        self.deleted: list[str] = []

    def put_object(self, *, Bucket, Key, Body, **_kwargs):
        assert Bucket == "test-bucket"
        self.objects[Key] = bytes(Body)

    def list_objects_v2(self, *, Bucket, Prefix, **_kwargs):
        assert Bucket == "test-bucket"
        return {
            "Contents": [
                {"Key": key}
                for key in sorted(self.objects)
                if key.startswith(Prefix)
            ],
            "IsTruncated": False,
        }

    def delete_objects(self, *, Bucket, Delete):
        assert Bucket == "test-bucket"
        for item in Delete["Objects"]:
            key = item["Key"]
            self.deleted.append(key)
            self.objects.pop(key, None)


def _handler(
    tmp_path: Path,
    client: FakeR2Client,
    *,
    max_bytes: int = 100 * 1024 * 1024,
) -> R2ProductionLogHandler:
    return R2ProductionLogHandler(
        client_factory=lambda: client,
        bucket="test-bucket",
        prefix="production-logs",
        max_bytes=max_bytes,
        retention_days=2,
        spool_dir=tmp_path,
        use_background_thread=False,
    )


def _record(
    message: str,
    *,
    level: int,
    created_at: datetime,
    lifecycle: bool = False,
    exc_info=None,
) -> logging.LogRecord:
    record = logging.LogRecord(
        name="jobportal.test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=exc_info,
    )
    record.created = created_at.timestamp()
    if lifecycle:
        record.r2_lifecycle = True
    return record


def test_stores_only_lifecycle_and_errors_with_tracebacks(tmp_path: Path):
    client = FakeR2Client()
    handler = _handler(tmp_path, client)
    current = datetime(2026, 7, 20, 12, 0, tzinfo=PKT)

    handler.emit(_record("ordinary request info", level=logging.INFO, created_at=current))
    handler.emit(
        _record(
            "server running",
            level=logging.INFO,
            created_at=current,
            lifecycle=True,
        )
    )
    try:
        raise RuntimeError("database exploded")
    except RuntimeError:
        import sys

        handler.emit(
            _record(
                "request failed",
                level=logging.ERROR,
                created_at=current,
                exc_info=sys.exc_info(),
            )
        )
    handler.close()

    assert len(client.objects) == 1
    key, payload = next(iter(client.objects.items()))
    text = payload.decode()
    assert key.startswith("production-logs/2026-07-20/backend-")
    assert "server running" in text
    assert "request failed" in text
    assert "Traceback (most recent call last)" in text
    assert "RuntimeError: database exploded" in text
    assert "ordinary request info" not in text


def test_rotates_before_an_r2_log_object_exceeds_limit(tmp_path: Path):
    client = FakeR2Client()
    handler = _handler(tmp_path, client, max_bytes=100)
    current = datetime(2026, 7, 20, 12, 0, tzinfo=PKT)

    handler.emit(
        _record(
            "x" * 260,
            level=logging.ERROR,
            created_at=current,
        )
    )
    handler.close()

    assert len(client.objects) >= 3
    assert all(len(payload) <= 100 for payload in client.objects.values())
    assert all("/2026-07-20/" in key for key in client.objects)


def test_retention_keeps_only_current_day_and_yesterday(tmp_path: Path):
    old_key = "production-logs/2026-07-18/backend-old-0001.log"
    yesterday_key = "production-logs/2026-07-19/backend-old-0001.log"
    unrelated_key = "job-portal/some-job/images/image.png"
    client = FakeR2Client([old_key, yesterday_key, unrelated_key])
    handler = _handler(tmp_path, client)
    current = datetime(2026, 7, 20, 0, 5, tzinfo=PKT)

    handler.emit(
        _record(
            "server running",
            level=logging.INFO,
            created_at=current,
            lifecycle=True,
        )
    )
    handler.close()

    assert old_key in client.deleted
    assert old_key not in client.objects
    assert yesterday_key in client.objects
    assert unrelated_key in client.objects
    assert any("production-logs/2026-07-20/" in key for key in client.objects)


def test_new_calendar_day_uses_a_new_folder(tmp_path: Path):
    client = FakeR2Client()
    handler = _handler(tmp_path, client)

    handler.emit(
        _record(
            "server running",
            level=logging.INFO,
            created_at=datetime(2026, 7, 19, 23, 59, tzinfo=PKT),
            lifecycle=True,
        )
    )
    handler.emit(
        _record(
            "server stopped",
            level=logging.INFO,
            created_at=datetime(2026, 7, 20, 0, 1, tzinfo=PKT),
            lifecycle=True,
        )
    )
    handler.close()

    assert any("production-logs/2026-07-19/" in key for key in client.objects)
    assert any("production-logs/2026-07-20/" in key for key in client.objects)


def test_background_uploader_flushes_before_shutdown(tmp_path: Path):
    client = FakeR2Client()
    handler = R2ProductionLogHandler(
        client_factory=lambda: client,
        bucket="test-bucket",
        prefix="production-logs",
        spool_dir=tmp_path,
        use_background_thread=True,
    )
    handler.emit(
        _record(
            "server running",
            level=logging.INFO,
            created_at=datetime(2026, 7, 20, 12, 0, tzinfo=PKT),
            lifecycle=True,
        )
    )

    handler.flush()
    handler.close()

    assert len(client.objects) == 1
    assert b"server running" in next(iter(client.objects.values()))
