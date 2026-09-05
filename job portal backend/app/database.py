from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

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
            raise RuntimeError(
                "SQLite is not supported; configure the Docker PostgreSQL database"
            )
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


def build_engine_options(url: str) -> dict:
    """Build SQLAlchemy options for local, dedicated, or serverless Postgres.

    Neon supplies its own PgBouncer-compatible pooled hostname. ``NullPool``
    prevents an idle Railway API process from holding TCP connections open and
    therefore allows Railway Serverless to sleep. Azure and local development
    retain the existing SQLAlchemy queue-pool behavior by default.
    """
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    options: dict = {"pool_pre_ping": True, "connect_args": connect_args}
    if not url.startswith("postgresql"):
        return options

    # Neon pooled connection strings contain ``-pooler``. Default them to
    # serverless mode so Railway processes do not keep database compute awake
    # between requests, while dedicated/local Postgres retains QueuePool.
    configured_pool_mode = os.getenv("DB_POOL_MODE", "auto").strip().lower()
    pool_mode = (
        "serverless"
        if configured_pool_mode == "auto" and "-pooler." in url.lower()
        else "queue"
        if configured_pool_mode == "auto"
        else configured_pool_mode
    )
    serverless = pool_mode in {"null", "serverless"}
    sslmode = os.getenv("DB_SSLMODE", "").strip()
    if sslmode:
        connect_args["sslmode"] = sslmode
        if not serverless:
            connect_args.update(
                {
                    "keepalives": 1,
                    "keepalives_idle": 30,
                    "keepalives_interval": 10,
                    "keepalives_count": 5,
                }
            )

    if serverless:
        options["poolclass"] = NullPool
        # A freshly-created connection cannot be stale. Avoid SQLAlchemy's
        # extra SELECT 1 on every request; Neon's pooler performs validation.
        options["pool_pre_ping"] = False
    else:
        options["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
        options["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "5"))
        options["pool_timeout"] = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        options["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "300"))
        # LIFO lets excess connections remain idle long enough to be closed,
        # which keeps the active database connection footprint small.
        options["pool_use_lifo"] = True
    return options


engine = create_engine(DATABASE_URL, **build_engine_options(DATABASE_URL))
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)

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
        "tool_pages",
        "tool_categories",
        "pages",
        "blog_posts",
        "jobs",
        "users",
        "password_reset_attempts",
        "analytics_visits",
        "infrastructure_cost_snapshots",
        "taxonomy_terms",
        "student_api_security_events",
        "subscriber_api_access",
        "email_subscribers",
        "subscription_email_deliveries",
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
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP NULL",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_token_hash VARCHAR(64) NULL",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_expires_at TIMESTAMP NULL",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_requested_at TIMESTAMP NULL",
        "ALTER TABLE seo_meta ADD COLUMN IF NOT EXISTS focus_keyword VARCHAR(200)",
        "ALTER TABLE seo_meta ADD COLUMN IF NOT EXISTS seo_score DOUBLE PRECISION",
        "ALTER TABLE seo_meta ADD COLUMN IF NOT EXISTS readability_score DOUBLE PRECISION",
        "ALTER TABLE seo_meta ADD COLUMN IF NOT EXISTS analysis JSON",
        "ALTER TABLE analytics_visits ADD COLUMN IF NOT EXISTS location_verified BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE analytics_visits ADD COLUMN IF NOT EXISTS city VARCHAR(150) NULL",
        "ALTER TABLE analytics_visits ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP NULL",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS provinces JSON NULL",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS newspaper VARCHAR(200) NOT NULL DEFAULT ''",
        "ALTER TABLE subscription_digest_runs ADD COLUMN IF NOT EXISTS job_id VARCHAR(36) NULL",
        "ALTER TABLE pages ADD COLUMN IF NOT EXISTS page_type VARCHAR(30) NOT NULL DEFAULT 'standard'",
        "ALTER TABLE pages ADD COLUMN IF NOT EXISTS taxonomy_value VARCHAR(300) NULL",
        "ALTER TABLE taxonomy_terms ADD COLUMN IF NOT EXISTS province VARCHAR(100) NULL",
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
            "ALTER TABLE analytics_visits ADD COLUMN city VARCHAR(150)",
            "ALTER TABLE analytics_visits ADD COLUMN last_seen_at DATETIME",
            "ALTER TABLE jobs ADD COLUMN provinces JSON",
            "ALTER TABLE jobs ADD COLUMN newspaper VARCHAR(200) NOT NULL DEFAULT ''",
            "ALTER TABLE subscription_digest_runs ADD COLUMN job_id VARCHAR(36)",
            "ALTER TABLE pages ADD COLUMN page_type VARCHAR(30) NOT NULL DEFAULT 'standard'",
            "ALTER TABLE pages ADD COLUMN taxonomy_value VARCHAR(300)",
            "ALTER TABLE taxonomy_terms ADD COLUMN province VARCHAR(100)",
        ]
    try:
        with engine.begin() as conn:
            insp = inspect(engine)
            if not {"seo_meta", "analytics_visits"}.intersection(
                insp.get_table_names()
            ):
                return
            for stmt in alters:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    pass
            # Existing analytics rows predate the dedicated presence timestamp.
            # Preserve their original visit time and initialize last_seen_at from it.
            conn.execute(
                text(
                    "UPDATE analytics_visits SET last_seen_at = visited_at "
                    "WHERE last_seen_at IS NULL"
                )
            )
            if not DATABASE_URL.startswith("sqlite"):
                conn.execute(
                    text(
                        "ALTER TABLE analytics_visits "
                        "ALTER COLUMN last_seen_at SET NOT NULL"
                    )
                )
                # Page slugs are unique inside their public route namespace, not
                # globally: /companies/dawn and /newspapers/dawn are both valid.
                conn.execute(text("ALTER TABLE pages DROP CONSTRAINT IF EXISTS pages_slug_key"))
                conn.execute(text("DROP INDEX IF EXISTS ix_pages_slug"))
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS "
                        "uq_subscription_digest_runs_job_id "
                        "ON subscription_digest_runs (job_id) WHERE job_id IS NOT NULL"
                    )
                )
                # Optional job fields use SQL NULL. Empty strings are neither
                # useful content nor valid structured-data values.
                conn.execute(text("ALTER TABLE jobs ALTER COLUMN newspaper DROP NOT NULL"))
                conn.execute(text("ALTER TABLE jobs ALTER COLUMN newspaper DROP DEFAULT"))
    except Exception:
        logger.exception("ensure_new_columns failed")


def _ensure_performance_indexes() -> None:
    """Install additive indexes for existing deployments without rebuilding tables."""
    statements = (
        "CREATE INDEX IF NOT EXISTS ix_analytics_visitor_path_visited "
        "ON analytics_visits (visitor_hash, path, visited_at)",
        "CREATE INDEX IF NOT EXISTS ix_analytics_verified_visitor_visited "
        "ON analytics_visits (visitor_hash, location_verified, visited_at)",
        "CREATE INDEX IF NOT EXISTS ix_analytics_visitor_path_last_seen "
        "ON analytics_visits (visitor_hash, path, last_seen_at)",
        "CREATE INDEX IF NOT EXISTS ix_analytics_visits_last_seen_at "
        "ON analytics_visits (last_seen_at)",
        "CREATE INDEX IF NOT EXISTS ix_jobs_published_created "
        "ON jobs (published_date, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_jobs_type_published "
        "ON jobs (job_type, published_date)",
        "CREATE INDEX IF NOT EXISTS ix_jobs_source_published "
        "ON jobs (source, published_date)",
        "CREATE INDEX IF NOT EXISTS ix_jobs_newspaper_published "
        "ON jobs (newspaper, published_date)",
        "CREATE INDEX IF NOT EXISTS ix_job_attachments_job_created "
        "ON job_attachments (job_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_job_qna_job_created "
        "ON job_qna (job_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_blog_public_published_created "
        "ON blog_posts (is_published, published_at, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_blog_updated ON blog_posts (updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_contact_messages_created "
        "ON contact_messages (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_seo_meta_entity "
        "ON seo_meta (entity_type, entity_id)",
        "CREATE INDEX IF NOT EXISTS ix_seo_meta_updated ON seo_meta (updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_taxonomy_kind_active_name "
        "ON taxonomy_terms (kind, is_active, name)",
        "CREATE INDEX IF NOT EXISTS ix_subscribers_active_subscribed "
        "ON email_subscribers (is_active, subscribed_at)",
        "CREATE INDEX IF NOT EXISTS ix_subscriber_api_access_active_key "
        "ON subscriber_api_access (is_key_active, api_key_hash)",
        "CREATE INDEX IF NOT EXISTS ix_subscriber_api_access_email_status "
        "ON subscriber_api_access (subscriber_email, subscriber_is_active)",
        "CREATE INDEX IF NOT EXISTS ix_student_api_security_scope_event_time "
        "ON student_api_security_events (scope_hash, event_type, occurred_at)",
        "CREATE INDEX IF NOT EXISTS ix_student_api_security_event_time "
        "ON student_api_security_events (event_type, occurred_at)",
        "CREATE INDEX IF NOT EXISTS ix_deliveries_due "
        "ON subscription_email_deliveries (status, next_attempt_at, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_deliveries_job_status "
        "ON subscription_email_deliveries (job_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_seo_backlinks_last_seen "
        "ON seo_backlinks (last_seen)",
        "CREATE INDEX IF NOT EXISTS ix_keyword_ranks_recorded_keyword "
        "ON seo_keyword_ranks (recorded_at, keyword)",
        "CREATE INDEX IF NOT EXISTS ix_pages_type_published_title "
        "ON pages (page_type, is_published, title)",
        "CREATE INDEX IF NOT EXISTS ix_tool_categories_public_order "
        "ON tool_categories (is_published, sort_order)",
        "CREATE INDEX IF NOT EXISTS ix_tool_pages_category_public_order "
        "ON tool_pages (category_id, is_published, sort_order)",
        "CREATE INDEX IF NOT EXISTS ix_pages_slug ON pages (slug)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_pages_type_slug "
        "ON pages (page_type, slug)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_pages_location_slug "
        "ON pages (slug) WHERE page_type IN ('city', 'province')",
    )
    try:
        existing_tables = set(inspect(engine).get_table_names())
        with engine.begin() as conn:
            for statement in statements:
                table_name = statement.rsplit(" ON ", 1)[1].split(" ", 1)[0]
                if table_name in existing_tables:
                    conn.execute(text(statement))
        logger.info("performance indexes ensured")
    except Exception:
        logger.exception("ensure_performance_indexes failed")
        raise


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
        _ensure_performance_indexes()
        logger.info("tables ensured")
    except Exception:
        logger.exception("init_db failed")
        raise


def configure_engine(url: str) -> None:
    global DATABASE_URL, engine, SessionLocal
    DATABASE_URL = url
    engine = create_engine(url, **build_engine_options(url))
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
    )
    logger.info("engine reconfigured url=%s", url)
