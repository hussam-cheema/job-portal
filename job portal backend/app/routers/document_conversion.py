from __future__ import annotations

import hashlib

from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.schemas import DocumentConversionJobCreated, DocumentConversionJobOut
from app.services.contact_security import client_ip
from app.services.document_conversion import (
    MAX_UPLOAD_BYTES,
    ConversionRejected,
    conversion_manager,
)

router = APIRouter()


def _ip_key(request: Request) -> str:
    return hashlib.sha256(client_ip(request).encode("utf-8")).hexdigest()


def _raise_http(exc: ConversionRejected) -> None:
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    raise HTTPException(status_code=exc.status_code, detail=exc.message, headers=headers)


@router.post(
    "/tools/document-converter/jobs",
    response_model=DocumentConversionJobCreated,
    status_code=202,
)
async def create_conversion_job(request: Request, file: UploadFile = File(...)):
    ip_key = _ip_key(request)
    try:
        if not getattr(request.state, "conversion_upload_authorized", False):
            await conversion_manager.authorize_upload(ip_key)
        chunks = bytearray()
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            chunks.extend(chunk)
            if len(chunks) >= MAX_UPLOAD_BYTES:
                raise ConversionRejected(
                    "The document must be smaller than 10 MB.",
                    status_code=413,
                )
        job, token = await conversion_manager.submit(
            filename=file.filename or "document",
            data=bytes(chunks),
            ip_key=ip_key,
        )
        return {**job.public_payload(), "access_token": token}
    except ConversionRejected as exc:
        _raise_http(exc)
    finally:
        await file.close()


@router.get(
    "/tools/document-converter/jobs/{job_id}",
    response_model=DocumentConversionJobOut,
)
async def conversion_job_status(
    job_id: str,
    access_token: str = Header(default="", alias="X-Conversion-Token"),
):
    try:
        job = await conversion_manager.get(job_id, access_token)
        return job.public_payload()
    except ConversionRejected as exc:
        _raise_http(exc)


@router.get("/tools/document-converter/jobs/{job_id}/download")
async def download_converted_document(
    job_id: str,
    access_token: str = Header(default="", alias="X-Conversion-Token"),
):
    try:
        path, filename, media_type = await conversion_manager.download(job_id, access_token)
        return FileResponse(
            path,
            media_type=media_type,
            filename=filename,
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )
    except ConversionRejected as exc:
        _raise_http(exc)
