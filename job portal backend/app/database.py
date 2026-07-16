from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.logging_config import get_logger

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_ROOT / ".env")

logger = get_logger("jobportal.database")

OBSOLETE_TABLES = (
    "agent_runs",
    "job_resources",
    "crawled_companies",
    "crawled_company",
)


def build_database_url_from_parts() -> str | None:
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "postgres")
    if user and password:
        return (
            f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(password)}"
            f"@{host}:{port}/{db}"
        )
    return None


def resolve_database_url() -> str:
    """Require Postgres for application runtime; allow SQLite only in automated tests."""
    is_test = os.getenv("JOBPORTAL_TESTING", "").lower() in {"1", "true", "yes"}
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        if env_url.startswith("postgresql://") and "+psycopg" not in env_url:
            env_url = env_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        if env_url.startswith("sqlite"):
            if is_test:
                return env_url
            raise RuntimeError("SQLite is not supported; configure the Docker PostgreSQL database")
        else:
            return env_url

    from_parts = build_database_url_from_parts()
    if from_parts:
        logger.info("built DATABASE_URL from POSTGRES_* env vars")
        return from_parts

    raise RuntimeError(
        "Docker PostgreSQL is required. Set DATABASE_URL or POSTGRES_USER/POSTGRES_PASSWORD "
        "with POSTGRES_HOST=postgres-db."
    )


DATABASE_URL = resolve_database_url()
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine_kwargs: dict = {"pool_pre_ping": True, "connect_args": connect_args}
if DATABASE_URL.startswith("postgresql"):
    sslmode = os.getenv("DB_SSLMODE", "").strip()
    if sslmode:
        connect_args.update(
            {
                "sslmode": sslmode,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            }
        )
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "5"))
    engine_kwargs["pool_timeout"] = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    engine_kwargs["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "300"))

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

logger.info(
    "database configured dialect=%s",
    "postgres" if DATABASE_URL.startswith("postgresql") else "sqlite",
)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        logger.exception("database session error")
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        db.close()


def _drop_obsolete_tables() -> None:
    try:
        insp = inspect(engine)
        existing = set(insp.get_table_names())
        with engine.begin() as conn:
            for name in OBSOLETE_TABLES:
                if name in existing:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
                    logger.info("dropped obsolete table %s", name)
    except Exception:
        logger.exception("drop_obsolete_tables failed")


def _jobs_schema_is_legacy() -> bool:
    try:
        insp = inspect(engine)
        if "jobs" not in insp.get_table_names():
            return False
        cols = {c["name"] for c in insp.get_columns("jobs")}
        if "slug" not in cols or "salary_range" not in cols:
            return True
        if "content_hash" in cols and "job_type" not in cols:
            return True
        return False
    except Exception:
        logger.exception("jobs schema inspect failed")
        return False


def _reset_app_tables() -> None:
    tables = (
        "seo_metrics",
        "seo_meta",
        "job_qna",
        "job_attachments",
        "contact_messages",
        "pages",
        "jobs",
        "users",
        "password_reset_attempts",
        "analytics_visits",
        "taxonomy_terms",
        "email_subscribers",
        "subscription_digest_runs",
        "agent_runs",
        "job_resources",
        "crawled_companies",
        "crawled_company",
    )
    try:
        with engine.begin() as conn:
            for name in tables:
                conn.execute(text(f'DROP TABLE IF EXISTS "{name}" CASCADE'))
        logger.info("reset app tables for new schema")
    except Exception:
        logger.exception("reset_app_tables failed")
        raise


def _ensure_new_columns() -> None:
    """Add columns/tables introduced after initial deploy (Postgres-safe)."""
    alters = [
        'ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 0',
        'ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0',
        'ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP NULL',
        'ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_token_hash VARCHAR(64) NULL',
        'ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_expires_at TIMESTAMP NULL',
        'ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_requested_at TIMESTAMP NULL',
        'ALTER TABLE seo_meta ADD COLUMN IF NOT EXISTS focus_keyword VARCHAR(200)',
        'ALTER TABLE seo_meta ADD COLUMN IF NOT EXISTS seo_score DOUBLE PRECISION',
        'ALTER TABLE seo_meta ADD COLUMN IF NOT EXISTS readability_score DOUBLE PRECISION',
        'ALTER TABLE seo_meta ADD COLUMN IF NOT EXISTS analysis JSON',
        'ALTER TABLE analytics_visits ADD COLUMN IF NOT EXISTS location_verified BOOLEAN NOT NULL DEFAULT FALSE',
    ]
    if DATABASE_URL.startswith("sqlite"):
        # SQLite lacks IF NOT EXISTS for columns — ignore errors
        alters = [
            "ALTER TABLE users ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN locked_at DATETIME",
            "ALTER TABLE users ADD COLUMN password_reset_token_hash VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN password_reset_expires_at DATETIME",
            "ALTER TABLE users ADD COLUMN password_reset_requested_at DATETIME",
            "ALTER TABLE seo_meta ADD COLUMN focus_keyword VARCHAR(200)",
            "ALTER TABLE seo_meta ADD COLUMN seo_score FLOAT",
            "ALTER TABLE seo_meta ADD COLUMN readability_score FLOAT",
            "ALTER TABLE seo_meta ADD COLUMN analysis JSON",
            "ALTER TABLE analytics_visits ADD COLUMN location_verified BOOLEAN NOT NULL DEFAULT FALSE",
        ]
    try:
        with engine.begin() as conn:
            insp = inspect(engine)
            if not {"seo_meta", "analytics_visits"}.intersection(insp.get_table_names()):
                return
            for stmt in alters:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    pass
    except Exception:
        logger.exception("ensure_new_columns failed")


def init_db() -> None:
    from app import models  # noqa: F401

    try:
        _drop_obsolete_tables()
        reset_requested = os.getenv("RESET_DB_SCHEMA", "").lower() in {
            "1",
            "true",
            "yes",
        }
        if reset_requested:
            logger.warning("RESET_DB_SCHEMA requested — recreating application tables")
            _reset_app_tables()
        elif _jobs_schema_is_legacy():
            raise RuntimeError(
                "Legacy jobs schema detected. Refusing to delete production data automatically. "
                "Back up the database and run an explicit migration, or set RESET_DB_SCHEMA=true "
                "once only if data loss is intended."
            )
        Base.metadata.create_all(bind=engine)
        _ensure_new_columns()
        logger.info("tables ensured")
    except Exception:
        logger.exception("init_db failed")
        raise


def configure_engine(url: str) -> None:
    global DATABASE_URL, engine, SessionLocal
    DATABASE_URL = url
    connect = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("engine reconfigured url=%s", url)
