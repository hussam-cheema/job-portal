from __future__ import annotations

from sqlalchemy.pool import NullPool

from app.database import build_engine_options


def test_serverless_pool_mode_uses_null_pool_without_keepalives(monkeypatch):
    monkeypatch.setenv("DB_POOL_MODE", "serverless")
    monkeypatch.setenv("DB_SSLMODE", "require")

    options = build_engine_options(
        "postgresql+psycopg2://example:secret@ep-example-pooler.test/neondb"
    )

    assert options["poolclass"] is NullPool
    assert options["connect_args"] == {"sslmode": "require"}
    assert "pool_size" not in options


def test_queue_pool_mode_preserves_dedicated_database_settings(monkeypatch):
    monkeypatch.setenv("DB_POOL_MODE", "queue")
    monkeypatch.setenv("DB_SSLMODE", "require")
    monkeypatch.setenv("DB_POOL_SIZE", "4")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "2")

    options = build_engine_options(
        "postgresql+psycopg2://example:secret@dedicated.test/postgres"
    )

    assert options["pool_size"] == 4
    assert options["max_overflow"] == 2
    assert options["connect_args"]["sslmode"] == "require"
    assert options["connect_args"]["keepalives"] == 1
