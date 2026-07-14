#!/usr/bin/env python3
from __future__ import annotations

import time

from sqlalchemy import text

from common import CheckFailed, add_backend_to_path, run


def check() -> str:
    add_backend_to_path()
    from app.database import DATABASE_URL, engine

    if not DATABASE_URL.startswith("postgresql"):
        raise CheckFailed("the configured database is not PostgreSQL")

    safe_target = engine.url.render_as_string(hide_password=True)
    print(f"[INFO] connecting to {safe_target}", flush=True)

    started = time.monotonic()
    try:
        with engine.connect() as connection:
            probe = connection.execute(text("SELECT 1")).scalar_one()
            if probe != 1:
                raise CheckFailed(f"database returned an unexpected probe value: {probe!r}")

            details = connection.execute(
                text(
                    "SELECT current_database(), current_user, "
                    "current_setting('server_version'), CURRENT_TIMESTAMP"
                )
            ).one()
            table_count = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            ).scalar_one()
    finally:
        engine.dispose()

    elapsed = time.monotonic() - started
    database, username, version, server_time = details
    return (
        f"PostgreSQL connection verified in {elapsed:.2f}s; "
        f"database={database}, user={username}, version={version}, "
        f"server_time={server_time.isoformat()}, public_tables={table_count}"
    )


if __name__ == "__main__":
    raise SystemExit(run(check))
