from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import init_db
from app.exceptions import (
    empty_filters,
    empty_job_list,
    empty_stats,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.logging_config import get_logger, setup_logging
from app.routers import analytics, auth, blog, contact, jobs, pages, seo, settings, stats, subscriptions, taxonomy, uploads
from app.seed import ensure_default_pages, seed_if_empty, sync_local_core_pages_once
from app.services.taxonomy import ensure_default_taxonomy
from app.services.watermark import migrate_legacy_job_watermarks

setup_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger("jobportal.main")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("startup begin")
    try:
        init_db()
        logger.info("database ready")
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            created = ensure_default_pages(db)
            locally_synced = sync_local_core_pages_once(db)
            taxonomy_created = ensure_default_taxonomy(db)
            watermarks_upgraded = migrate_legacy_job_watermarks(db)
            db.commit()
            if created:
                logger.info("core CMS pages created count=%s", len(created))
            if locally_synced:
                logger.info("local CMS pages synchronized count=%s", len(locally_synced))
            if taxonomy_created:
                logger.info("taxonomy terms created count=%s", len(taxonomy_created))
            if watermarks_upgraded:
                logger.info(
                    "legacy job description watermarks upgraded count=%s",
                    watermarks_upgraded,
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

    logger.info("startup complete")
    yield
    logger.info("shutdown")


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


@app.get("/sitemap.xml", tags=["seo"], response_class=None)
def root_sitemap():
    """Google-friendly sitemap at site root (API host)."""
    from fastapi.responses import Response

    from app.database import SessionLocal
    from app.services.seo_tools import build_sitemap_urls

    db = SessionLocal()
    try:
        urls = build_sitemap_urls(db)
        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]
        for u in urls:
            parts.append("<url>")
            parts.append(f"<loc>{u['loc']}</loc>")
            if u.get("lastmod"):
                parts.append(f"<lastmod>{u['lastmod']}</lastmod>")
            if u.get("changefreq"):
                parts.append(f"<changefreq>{u['changefreq']}</changefreq>")
            if u.get("priority") is not None:
                parts.append(f"<priority>{u['priority']}</priority>")
            parts.append("</url>")
        parts.append("</urlset>")
        return Response(content="\n".join(parts), media_type="application/xml")
    except Exception:
        logger.exception("root sitemap failed")
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>',
            media_type="application/xml",
        )
    finally:
        db.close()


@app.get("/robots.txt", tags=["seo"])
def root_robots():
    from fastapi.responses import PlainTextResponse

    from app.services.seo_tools import robots_txt

    return PlainTextResponse(robots_txt())


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
