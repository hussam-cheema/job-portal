from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import canonical_site_url
from app.database import init_db
from app.exceptions import (
    empty_filters,
    empty_job_list,
    empty_stats,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.logging_config import flush_production_logs, get_logger, setup_logging
from app.routers import (
    analytics,
    auth,
    blog,
    contact,
    infrastructure,
    jobs,
    pages,
    seo,
    settings,
    stats,
    subscriptions,
    taxonomy,
    uploads,
)
from app.seed import (
    ensure_default_pages,
    seed_if_empty,
    sync_core_page_content_v2,
    sync_core_page_content_v3,
    sync_homepage_branding_seo_v1,
    sync_local_core_pages_once,
    sync_taxonomy_pages_v1,
    sync_directory_page_slugs_v2,
    sync_job_directory_pages_v3,
)
from app.services.taxonomy import ensure_default_taxonomy
from app.services.watermark import migrate_legacy_job_watermarks

setup_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger("jobportal.main")


def _warm_embedding_cache_in_background() -> None:
    if os.getenv("JOBPORTAL_TESTING", "").lower() in {"1", "true", "yes"}:
        return
    if os.getenv("QWEN3_EMBEDDING_CACHE_BACKGROUND", "true").lower() not in {
        "1",
        "true",
        "yes",
    }:
        return

    def warm() -> None:
        try:
            from app.services.model_cache import ensure_local_embedding_model

            ensure_local_embedding_model()
        except Exception:
            logger.exception("background embedding model warmup failed")

    threading.Thread(
        target=warm,
        name="embedding-model-warmup",
        daemon=True,
    ).start()


def _start_newsletter_retry_worker() -> tuple[threading.Event, threading.Thread] | None:
    if os.getenv("JOBPORTAL_TESTING", "").lower() in {"1", "true", "yes"}:
        return None
    if os.getenv("NEWSLETTER_RETRY_ENABLED", "true").lower() not in {
        "1",
        "true",
        "yes",
    }:
        return None

    stop_event = threading.Event()
    interval = max(
        15,
        min(3600, int(os.getenv("NEWSLETTER_RETRY_INTERVAL_SECONDS", "60"))),
    )

    def run() -> None:
        from app.database import SessionLocal
        from app.services.newsletter import process_pending_job_alerts

        while not stop_event.is_set():
            db = SessionLocal()
            try:
                result = process_pending_job_alerts(db)
                if result["processed_count"]:
                    logger.info(
                        "newsletter retry worker processed=%s delivered=%s",
                        result["processed_count"],
                        result["delivered_count"],
                    )
            except Exception:
                db.rollback()
                logger.exception("newsletter retry worker failed")
            finally:
                db.close()
            stop_event.wait(interval)

    thread = threading.Thread(
        target=run,
        name="newsletter-delivery-retry",
        daemon=True,
    )
    thread.start()
    return stop_event, thread


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("server starting", extra={"r2_lifecycle": True})
    try:
        init_db()
        logger.info("database ready")
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            created = ensure_default_pages(db)
            locally_synced = sync_local_core_pages_once(db)
            content_synced = sync_core_page_content_v2(db)
            ats_content_synced = sync_core_page_content_v3(db)
            branding_synced = sync_homepage_branding_seo_v1(db)
            taxonomy_created = ensure_default_taxonomy(db)
            watermarks_upgraded = migrate_legacy_job_watermarks(db)
            career_guides_created = []
            if os.getenv("JOBPORTAL_TESTING", "").lower() not in {"1", "true", "yes"}:
                from app.services.career_guide_seed import publish_career_guides_once

                career_guides_created = publish_career_guides_once(db)
            db.commit()
            if created:
                logger.info("core CMS pages created count=%s", len(created))
            if locally_synced:
                logger.info("local CMS pages synchronized count=%s", len(locally_synced))
            if content_synced:
                logger.info("core CMS content and SEO upgraded count=%s", len(content_synced))
            if ats_content_synced:
                logger.info("ATS Resume Builder disclosures published count=%s", len(ats_content_synced))
            if branding_synced:
                logger.info("homepage branding and SEO upgraded count=%s", len(branding_synced))
            if taxonomy_created:
                logger.info("taxonomy terms created count=%s", len(taxonomy_created))
            if watermarks_upgraded:
                logger.info(
                    "legacy job description watermarks upgraded count=%s",
                    watermarks_upgraded,
                )
            if career_guides_created:
                logger.info(
                    "career guide articles published count=%s",
                    len(career_guides_created),
                )
        finally:
            db.close()
    except Exception:
        logger.exception("database init failed — API will use empty fallbacks")

    if os.getenv("SEED_ON_STARTUP", "true").lower() in {"1", "true", "yes"}:
        try:
            seed_if_empty()
        except Exception:
            logger.exception("seed failed — continuing")
    else:
        logger.info("seed skipped (SEED_ON_STARTUP=false)")

    try:
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            taxonomy_pages_created = sync_taxonomy_pages_v1(db)
            directory_slugs_updated = sync_directory_page_slugs_v2(db)
            job_directory_pages_created = sync_job_directory_pages_v3(db)
            db.commit()
            if taxonomy_pages_created:
                logger.info(
                    "taxonomy CMS pages created count=%s",
                    len(taxonomy_pages_created),
                )
            if directory_slugs_updated:
                logger.info(
                    "directory CMS page slugs normalized count=%s",
                    len(directory_slugs_updated),
                )
            if job_directory_pages_created:
                logger.info(
                    "job directory CMS pages reconciled count=%s",
                    len(job_directory_pages_created),
                )
        finally:
            db.close()
    except Exception:
        logger.exception("taxonomy CMS page migration failed — continuing")

    # The embedding model is only needed by the admin Q&A workflow. Warming it
    # asynchronously keeps public traffic from waiting for the Azure Files
    # mount/model cache during a Container Apps cold start.
    _warm_embedding_cache_in_background()
    newsletter_worker = _start_newsletter_retry_worker()
    logger.info("server running", extra={"r2_lifecycle": True})
    try:
        yield
    finally:
        if newsletter_worker:
            stop_event, thread = newsletter_worker
            stop_event.set()
            thread.join(timeout=2)
        logger.info("server stopped", extra={"r2_lifecycle": True})
        flush_production_logs()


app = FastAPI(
    title="Job Portal API",
    description="Pakistani job listings API — manual admin posting + YouTube QnA",
    version="2.0.0",
    lifespan=lifespan,
)

cors_raw = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
)
origins = [o.strip() for o in cors_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_write_freeze(request: Request, call_next):
    """Temporarily reject writes while a final database snapshot is copied.

    Public reads remain available throughout the cutover. The flag is normally
    false and is enabled only for the short final synchronization window.
    """
    freeze_enabled = os.getenv("WRITE_FREEZE_ENABLED", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    if freeze_enabled and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "A brief maintenance synchronization is in progress. Please retry.",
                "code": "write_freeze",
            },
            headers={"Retry-After": "30"},
        )
    return await call_next(request)


@app.middleware("http")
async def prevent_api_indexing(request: Request, call_next):
    """Keep JSON/API utility URLs out of search without blocking crawlers from seeing the rule."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/media/"):
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(pages.router, prefix="/api", tags=["pages"])
app.include_router(blog.router, prefix="/api", tags=["blog"])
app.include_router(contact.router, prefix="/api", tags=["contact"])
app.include_router(uploads.router, prefix="/api", tags=["uploads"])
app.include_router(seo.router, prefix="/api", tags=["seo"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(analytics.router, prefix="/api", tags=["analytics"])
app.include_router(taxonomy.router, prefix="/api", tags=["taxonomy"])
app.include_router(subscriptions.router, prefix="/api", tags=["subscriptions"])
app.include_router(infrastructure.router, prefix="/api", tags=["infrastructure"])


@app.get("/sitemap.xml", tags=["seo"])
def root_sitemap():
    """Keep one authoritative sitemap on the public website host."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(f"{canonical_site_url()}/sitemap.xml", status_code=308)


@app.get("/robots.txt", tags=["seo"])
def root_robots():
    from fastapi.responses import PlainTextResponse

    # The public website owns the canonical sitemap and its own robots.txt.
    # This host is an API, so let crawlers reach responses and read their
    # X-Robots-Tag instead of advertising frontend URLs from the API origin.
    return PlainTextResponse("User-agent: *\nAllow: /\n")


@app.get("/", tags=["meta"])
def root():
    return {
        "name": "Job Portal API",
        "status": "ok",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "jobs": "/api/jobs",
            "login": "/api/auth/login",
            "admin": "/api/admin/*",
            "contact": "/api/contact",
            "pages": "/api/pages",
        },
        "ui": "http://localhost:3000",
    }


@app.get("/health", tags=["meta"])
def health():
    try:
        from sqlalchemy import text

        from app.database import SessionLocal

        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_ok = True
        finally:
            db.close()
    except Exception as exc:
        logger.warning("health db check failed: %s", exc)
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "up" if db_ok else "down",
        "fallback": "empty_responses" if not db_ok else None,
    }


@app.get("/ready", tags=["meta"])
def readiness():
    """Readiness probe: fail routing/deployment checks while PostgreSQL is unavailable."""
    try:
        from sqlalchemy import text

        from app.database import SessionLocal

        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        return {"status": "ready", "database": "up"}
    except Exception as exc:
        logger.warning("readiness db check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "down"},
        )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("request %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request failed %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "path": request.url.path,
            },
        )
    if response.status_code >= 400:
        logger.warning(
            "response %s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
        )
    return response


@app.get("/api/empty/jobs", include_in_schema=False)
def fallback_jobs():
    return empty_job_list()


@app.get("/api/empty/filters", include_in_schema=False)
def fallback_filters():
    return empty_filters()


@app.get("/api/empty/stats", include_in_schema=False)
def fallback_stats():
    return empty_stats()
