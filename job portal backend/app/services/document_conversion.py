from __future__ import annotations

import asyncio
import hashlib
import io
import math
import os
import re
import secrets
import shutil
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import uuid4

import pymupdf

from app.logging_config import get_logger

logger = get_logger("jobportal.document_conversion")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = max(1, min(500, int(os.getenv("CONVERTER_MAX_PDF_PAGES", "200"))))
MAX_DOCX_ENTRIES = 5_000
MAX_DOCX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_OUTPUT_BYTES = 100 * 1024 * 1024
JOB_TTL_SECONDS = max(300, min(3600, int(os.getenv("CONVERTER_JOB_TTL_SECONDS", "900"))))
CONVERSION_TIMEOUT_SECONDS = max(
    30,
    min(600, int(os.getenv("CONVERTER_TIMEOUT_SECONDS", "180"))),
)
MAX_CONCURRENT_JOBS = max(1, min(4, int(os.getenv("CONVERTER_MAX_CONCURRENT", "2"))))
MAX_PENDING_JOBS = max(
    MAX_CONCURRENT_JOBS,
    min(30, int(os.getenv("CONVERTER_MAX_PENDING", "12"))),
)
MAX_ACTIVE_PER_IP = max(1, min(3, int(os.getenv("CONVERTER_MAX_PER_IP", "2"))))

JobStatus = Literal["queued", "converting", "verifying", "completed", "failed"]
DocumentFormat = Literal["pdf", "docx"]


class ConversionRejected(Exception):
    def __init__(self, message: str, *, status_code: int = 400, retry_after: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after


@dataclass
class UploadDetails:
    input_format: DocumentFormat
    output_format: DocumentFormat
    page_count: int
    output_filename: str


@dataclass
class ConversionJob:
    job_id: str
    token_hash: str
    ip_key: str
    work_dir: Path
    input_path: Path
    output_path: Path
    input_format: DocumentFormat
    output_format: DocumentFormat
    output_filename: str
    page_count: int
    status: JobStatus = "queued"
    progress: int = 25
    stage: str = "Queued securely"
    estimated_seconds_remaining: int | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(
        default_factory=lambda: datetime.utcnow() + timedelta(seconds=JOB_TTL_SECONDS)
    )

    def public_payload(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "input_format": self.input_format,
            "output_format": self.output_format,
            "output_filename": self.output_filename,
            "estimated_seconds_remaining": self.estimated_seconds_remaining,
            "error": self.error,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


@dataclass
class _TokenBucket:
    tokens: float
    updated_at: float


def _safe_output_name(original_name: str, extension: str) -> str:
    stem = Path(original_name or "document").stem
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "", stem).strip(" ._-")[:80]
    return f"{stem or 'document'}.{extension}"


def _validate_pdf(data: bytes) -> int:
    if not data.startswith(b"%PDF-"):
        raise ConversionRejected(
            "The file extension says PDF, but the document content is not a valid PDF."
        )
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ConversionRejected("This PDF is damaged or cannot be read.") from exc
    try:
        if document.needs_pass or document.is_encrypted:
            raise ConversionRejected("Password-protected or encrypted PDFs are not supported.")
        page_count = document.page_count
        if page_count < 1:
            raise ConversionRejected("This PDF has no pages to convert.")
        if page_count > MAX_PDF_PAGES:
            raise ConversionRejected(
                f"PDFs are limited to {MAX_PDF_PAGES} pages for safe processing."
            )
        return page_count
    finally:
        document.close()


def _validate_docx(data: bytes) -> int:
    if not data.startswith(b"PK") or not zipfile.is_zipfile(io.BytesIO(data)):
        raise ConversionRejected(
            "The file extension says DOCX, but the document content is not a valid DOCX file."
        )
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES:
                raise ConversionRejected("This DOCX contains too many embedded items.")
            names = {entry.filename for entry in entries}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise ConversionRejected("This file is not a valid Word DOCX document.")
            if any(
                entry.filename == "word/vbaProject.bin"
                or "macros" in entry.filename.lower()
                for entry in entries
            ):
                raise ConversionRejected("Macro-enabled Word documents are not supported.")
            if any(
                entry.filename.startswith(("/", "\\"))
                or ".." in PurePosixPath(entry.filename).parts
                for entry in entries
            ):
                raise ConversionRejected("This DOCX contains unsafe file paths.")
            uncompressed = sum(entry.file_size for entry in entries)
            compressed = sum(entry.compress_size for entry in entries)
            if uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise ConversionRejected("This DOCX expands beyond the safe processing limit.")
            if uncompressed / max(1, compressed) > 150:
                raise ConversionRejected("This DOCX has an unsafe compression ratio.")
            if archive.testzip() is not None:
                raise ConversionRejected("This DOCX is damaged or incomplete.")
            document_xml = archive.read("word/document.xml")
            explicit_page_breaks = document_xml.count(b'w:type="page"')
            return max(1, explicit_page_breaks + 1)
    except ConversionRejected:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ConversionRejected("This DOCX is damaged or cannot be read.") from exc


def validate_upload(filename: str, data: bytes) -> UploadDetails:
    if not data:
        raise ConversionRejected("Choose a PDF or DOCX document before converting.")
    if len(data) >= MAX_UPLOAD_BYTES:
        raise ConversionRejected(
            "The document must be smaller than 10 MB.",
            status_code=413,
        )
    extension = Path(filename or "").suffix.lower().lstrip(".")
    if extension not in {"pdf", "docx"}:
        raise ConversionRejected(
            "This document type is not allowed. Upload one PDF or DOCX file."
        )
    if extension == "pdf":
        pages = _validate_pdf(data)
        output_format: DocumentFormat = "docx"
    else:
        pages = _validate_docx(data)
        output_format = "pdf"
    return UploadDetails(
        input_format=extension,  # type: ignore[arg-type]
        output_format=output_format,
        page_count=pages,
        output_filename=_safe_output_name(filename, output_format),
    )


class DocumentConversionManager:
    def __init__(self) -> None:
        self._jobs: dict[str, ConversionJob] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._buckets: dict[str, _TokenBucket] = {}
        self._active_by_ip: dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

    async def authorize_upload(self, ip_key: str) -> None:
        """Token bucket: three immediate uploads, then one token every two minutes."""
        async with self._lock:
            self._prune_locked()
            now = time.monotonic()
            bucket = self._buckets.get(ip_key, _TokenBucket(tokens=3.0, updated_at=now))
            bucket.tokens = min(3.0, bucket.tokens + (now - bucket.updated_at) / 120.0)
            bucket.updated_at = now
            if bucket.tokens < 1.0:
                retry_after = max(1, math.ceil((1.0 - bucket.tokens) * 120.0))
                self._buckets[ip_key] = bucket
                raise ConversionRejected(
                    "Too many conversion uploads. Please wait before trying again.",
                    status_code=429,
                    retry_after=retry_after,
                )
            bucket.tokens -= 1.0
            self._buckets[ip_key] = bucket

    async def submit(
        self,
        *,
        filename: str,
        data: bytes,
        ip_key: str,
    ) -> tuple[ConversionJob, str]:
        details = validate_upload(filename, data)
        async with self._lock:
            self._prune_locked()
            pending = sum(
                job.status in {"queued", "converting", "verifying"}
                for job in self._jobs.values()
            )
            if pending >= MAX_PENDING_JOBS:
                raise ConversionRejected(
                    "The converter is busy. Please retry in a moment.",
                    status_code=503,
                    retry_after=20,
                )
            if self._active_by_ip.get(ip_key, 0) >= MAX_ACTIVE_PER_IP:
                raise ConversionRejected(
                    "You already have the maximum number of conversions in progress.",
                    status_code=429,
                    retry_after=30,
                )

            work_dir = Path(tempfile.mkdtemp(prefix="pjm-convert-"))
            input_path = work_dir / f"input.{details.input_format}"
            output_path = work_dir / f"output.{details.output_format}"
            try:
                input_path.write_bytes(data)
            except Exception:
                shutil.rmtree(work_dir, ignore_errors=True)
                raise

            token = secrets.token_urlsafe(32)
            job = ConversionJob(
                job_id=str(uuid4()),
                token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                ip_key=ip_key,
                work_dir=work_dir,
                input_path=input_path,
                output_path=output_path,
                input_format=details.input_format,
                output_format=details.output_format,
                output_filename=details.output_filename,
                page_count=details.page_count,
                estimated_seconds_remaining=self._estimate_seconds(details),
            )
            self._jobs[job.job_id] = job
            self._active_by_ip[ip_key] = self._active_by_ip.get(ip_key, 0) + 1
            task = asyncio.create_task(self._run(job))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            return job, token

    async def get(self, job_id: str, token: str) -> ConversionJob:
        async with self._lock:
            self._prune_locked()
            job = self._jobs.get(job_id)
            if not job or not self._token_matches(job, token):
                raise ConversionRejected("Conversion job not found.", status_code=404)
            return job

    async def download(self, job_id: str, token: str) -> tuple[Path, str, str]:
        job = await self.get(job_id, token)
        if job.status != "completed" or not job.output_path.is_file():
            raise ConversionRejected("The converted document is not ready yet.", status_code=409)
        media_type = (
            "application/pdf"
            if job.output_format == "pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        return job.output_path, job.output_filename, media_type

    async def shutdown(self) -> None:
        for task in tuple(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
        async with self._lock:
            for job in self._jobs.values():
                shutil.rmtree(job.work_dir, ignore_errors=True)
            self._jobs.clear()
            self._active_by_ip.clear()
            self._buckets.clear()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

    async def reset_for_tests(self) -> None:
        await self.shutdown()

    @staticmethod
    def _token_matches(job: ConversionJob, token: str) -> bool:
        supplied = hashlib.sha256((token or "").encode("utf-8")).hexdigest()
        return secrets.compare_digest(job.token_hash, supplied)

    @staticmethod
    def _estimate_seconds(details: UploadDetails) -> int:
        per_page = 2.0 if details.input_format == "pdf" else 0.8
        return max(5, min(CONVERSION_TIMEOUT_SECONDS, math.ceil(4 + details.page_count * per_page)))

    def _prune_locked(self) -> None:
        now = datetime.utcnow()
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if job.expires_at <= now
            and job.status not in {"queued", "converting", "verifying"}
        ]
        for job_id in expired:
            job = self._jobs.pop(job_id)
            shutil.rmtree(job.work_dir, ignore_errors=True)

    async def _run(self, job: ConversionJob) -> None:
        try:
            async with self._semaphore:
                job.status = "converting"
                job.progress = 35
                job.stage = f"Converting {job.input_format.upper()} to {job.output_format.upper()}"
                started_at = time.monotonic()
                ticker = asyncio.create_task(self._tick_progress(job, started_at))
                try:
                    if job.input_format == "docx":
                        await self._docx_to_pdf(job)
                    else:
                        await self._pdf_to_docx(job)
                finally:
                    ticker.cancel()
                    await asyncio.gather(ticker, return_exceptions=True)

                job.status = "verifying"
                job.progress = 90
                job.stage = "Verifying converted document"
                job.estimated_seconds_remaining = 2
                await asyncio.to_thread(self._verify_output, job)
                job.input_path.unlink(missing_ok=True)
                shutil.rmtree(job.work_dir / "lo-profile", ignore_errors=True)
                job.status = "completed"
                job.progress = 100
                job.stage = "Ready to download"
                job.estimated_seconds_remaining = 0
                job.expires_at = datetime.utcnow() + timedelta(seconds=JOB_TTL_SECONDS)
                logger.info(
                    "document conversion completed job=%s direction=%s_to_%s pages=%s",
                    job.job_id,
                    job.input_format,
                    job.output_format,
                    job.page_count,
                )
        except asyncio.CancelledError:
            shutil.rmtree(job.work_dir, ignore_errors=True)
            raise
        except Exception as exc:
            logger.warning(
                "document conversion failed job=%s direction=%s_to_%s error=%s",
                job.job_id,
                job.input_format,
                job.output_format,
                type(exc).__name__,
            )
            job.status = "failed"
            job.progress = 100
            job.stage = "Conversion could not be completed"
            job.estimated_seconds_remaining = 0
            job.error = self._friendly_conversion_error(exc)
            job.expires_at = datetime.utcnow() + timedelta(seconds=JOB_TTL_SECONDS)
            shutil.rmtree(job.work_dir, ignore_errors=True)
        finally:
            async with self._lock:
                remaining = max(0, self._active_by_ip.get(job.ip_key, 1) - 1)
                if remaining:
                    self._active_by_ip[job.ip_key] = remaining
                else:
                    self._active_by_ip.pop(job.ip_key, None)

    async def _tick_progress(self, job: ConversionJob, started_at: float) -> None:
        estimate = max(5, job.estimated_seconds_remaining or 10)
        while True:
            await asyncio.sleep(0.75)
            elapsed = time.monotonic() - started_at
            fraction = min(0.98, elapsed / estimate)
            job.progress = min(85, max(job.progress, 35 + int(fraction * 50)))
            job.estimated_seconds_remaining = max(1, math.ceil(estimate - elapsed))

    async def _docx_to_pdf(self, job: ConversionJob) -> None:
        executable = shutil.which("soffice") or shutil.which("libreoffice")
        if not executable:
            raise RuntimeError("LibreOffice is unavailable")
        profile_dir = job.work_dir / "lo-profile"
        profile_dir.mkdir()
        command = [
            executable,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            "--norestore",
            f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(job.work_dir),
            str(job.input_path),
        ]
        await self._run_subprocess(command)
        generated = job.work_dir / "input.pdf"
        if generated != job.output_path and generated.is_file():
            generated.replace(job.output_path)

    async def _pdf_to_docx(self, job: ConversionJob) -> None:
        command = [
            sys.executable,
            "-m",
            "app.services.pdf_to_docx_worker",
            str(job.input_path),
            str(job.output_path),
        ]
        await self._run_subprocess(command)

    @staticmethod
    async def _run_subprocess(command: list[str]) -> None:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=CONVERSION_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise RuntimeError("Conversion timed out")
        if process.returncode != 0:
            detail = (stderr or stdout).decode("utf-8", errors="replace")[-1_000:]
            logger.debug("converter subprocess failed detail=%s", detail)
            raise RuntimeError("Converter process failed")

    @staticmethod
    def _verify_output(job: ConversionJob) -> None:
        if not job.output_path.is_file() or job.output_path.stat().st_size < 20:
            raise RuntimeError("Converted output is empty")
        if job.output_path.stat().st_size > MAX_OUTPUT_BYTES:
            raise RuntimeError("Converted output is too large")
        data = job.output_path.read_bytes()
        if job.output_format == "pdf":
            _validate_pdf(data)
        else:
            _validate_docx(data)

    @staticmethod
    def _friendly_conversion_error(exc: Exception) -> str:
        text = str(exc).lower()
        if "timed out" in text:
            return "The document took too long to convert. Try a smaller or simpler file."
        return (
            "This document could not be converted safely. It may be damaged, scanned, "
            "password-protected, or use unsupported document features."
        )


conversion_manager = DocumentConversionManager()
