from __future__ import annotations

import asyncio
import io
import os
import shutil
import zipfile
from pathlib import Path

os.environ.setdefault("SEED_ON_STARTUP", "false")
os.environ.setdefault("JOBPORTAL_TESTING", "true")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret-with-at-least-thirty-two-characters")

import pymupdf
import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.services.document_conversion import (
    MAX_UPLOAD_BYTES,
    ConversionRejected,
    conversion_manager,
    validate_upload,
)


def _pdf_bytes(text: str = "PDF conversion fidelity marker") -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 100), text)
    data = document.tobytes()
    document.close()
    return data


def _docx_bytes(text: str = "DOCX conversion fidelity marker") -> bytes:
    stream = io.BytesIO()
    document = Document()
    document.add_heading("Conversion test", level=1)
    document.add_paragraph(text)
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Column A"
    table.cell(0, 1).text = "Column B"
    table.cell(1, 0).text = "Alpha"
    table.cell(1, 1).text = "Beta"
    document.save(stream)
    return stream.getvalue()


def test_upload_validation_rejects_type_spoofing_size_and_unsafe_docx():
    with pytest.raises(ConversionRejected, match="not allowed"):
        validate_upload("payload.exe", b"MZ")
    with pytest.raises(ConversionRejected, match="content is not a valid PDF"):
        validate_upload("fake.pdf", _docx_bytes())
    with pytest.raises(ConversionRejected, match="smaller than 10 MB"):
        validate_upload("large.pdf", b"%PDF-" + b"0" * MAX_UPLOAD_BYTES)

    unsafe = io.BytesIO()
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
        archive.writestr("word/vbaProject.bin", b"macro")
    with pytest.raises(ConversionRejected, match="Macro-enabled"):
        validate_upload("unsafe.docx", unsafe.getvalue())


def test_api_is_async_and_requires_an_unpredictable_job_token(monkeypatch: pytest.MonkeyPatch):
    async def fake_docx_to_pdf(job):
        output = pymupdf.open()
        page = output.new_page()
        page.insert_text((72, 100), "Converted asynchronously")
        output.save(job.output_path)
        output.close()

    monkeypatch.setattr(conversion_manager, "_docx_to_pdf", fake_docx_to_pdf)
    with TestClient(app) as client:
        created = client.post(
            "/api/tools/document-converter/jobs",
            files={
                "file": (
                    "sample.docx",
                    _docx_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert created.status_code == 202
        payload = created.json()
        assert payload["access_token"]
        assert payload["output_format"] == "pdf"

        hidden = client.get(f"/api/tools/document-converter/jobs/{payload['job_id']}")
        assert hidden.status_code == 404

        headers = {"X-Conversion-Token": payload["access_token"]}
        for _ in range(30):
            status = client.get(
                f"/api/tools/document-converter/jobs/{payload['job_id']}",
                headers=headers,
            )
            assert status.status_code == 200
            if status.json()["status"] == "completed":
                break
            import time

            time.sleep(0.05)
        assert status.json()["status"] == "completed"
        assert status.json()["progress"] == 100
        downloaded = client.get(
            f"/api/tools/document-converter/jobs/{payload['job_id']}/download",
            headers=headers,
        )
        assert downloaded.status_code == 200
        assert downloaded.content.startswith(b"%PDF-")
        assert downloaded.headers["cache-control"] == "private, no-store"


def test_token_bucket_limits_upload_floods():
    async def exercise() -> None:
        await conversion_manager.reset_for_tests()
        for _ in range(3):
            await conversion_manager.authorize_upload("same-network")
        with pytest.raises(ConversionRejected) as caught:
            await conversion_manager.authorize_upload("same-network")
        assert caught.value.status_code == 429
        assert caught.value.retry_after
        await conversion_manager.reset_for_tests()

    asyncio.run(exercise())


@pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice is not installed")
def test_real_docx_to_pdf_and_pdf_to_docx_preserve_document_content():
    async def wait_for_job(filename: str, data: bytes):
        await conversion_manager.authorize_upload(f"integration-{filename}")
        job, token = await conversion_manager.submit(
            filename=filename,
            data=data,
            ip_key=f"integration-{filename}",
        )
        for _ in range(360):
            current = await conversion_manager.get(job.job_id, token)
            if current.status in {"completed", "failed"}:
                return current
            await asyncio.sleep(0.25)
        raise AssertionError("conversion did not finish")

    async def exercise() -> None:
        await conversion_manager.reset_for_tests()
        docx_job = await wait_for_job("source.docx", _docx_bytes())
        assert docx_job.status == "completed", docx_job.error
        converted_pdf = pymupdf.open(docx_job.output_path)
        pdf_text = "\n".join(page.get_text() for page in converted_pdf)
        converted_pdf.close()
        assert "DOCX conversion fidelity marker" in pdf_text
        assert "Column A" in pdf_text and "Beta" in pdf_text

        pdf_job = await wait_for_job("source.pdf", _pdf_bytes())
        assert pdf_job.status == "completed", pdf_job.error
        with zipfile.ZipFile(pdf_job.output_path) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        assert "PDF conversion fidelity marker" in document_xml
        await conversion_manager.reset_for_tests()

    asyncio.run(exercise())
