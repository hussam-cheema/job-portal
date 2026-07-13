from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import get_logger

logger = get_logger("jobportal.exceptions")


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        status = getattr(exc, "status_code", 500)
        detail = getattr(exc, "detail", "Error")
        if status >= 500:
            logger.error("http_error path=%s status=%s detail=%s", request.url.path, status, detail)
        else:
            logger.warning("http_error path=%s status=%s detail=%s", request.url.path, status, detail)
        return JSONResponse(
            status_code=status,
            content={"detail": detail, "path": str(request.url.path)},
        )
    return await unhandled_exception_handler(request, exc)


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    errors: Any = []
    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
    logger.warning("validation_error path=%s errors=%s", request.url.path, errors)
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": errors, "path": str(request.url.path)},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error path=%s error=%s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "path": str(request.url.path),
            "fallback": "empty",
        },
    )


def empty_job_list(page: int = 1, page_size: int = 20) -> dict:
    return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}


def empty_filters() -> dict:
    return {
        "source_types": [],
        "sectors": ["govt", "private"],
        "categories": [],
        "cities": [],
        "companies": [],
        "employment_types": [],
        "tags": [],
        "job_types": ["government", "private"],
    }


def empty_stats() -> dict:
    return {
        "total_jobs": 0,
        "open_for_apply": 0,
        "by_source_type": {},
        "by_category": {},
        "by_city": {},
        "by_job_type": {},
        "last_updated": None,
    }
