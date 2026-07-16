from __future__ import annotations

from unittest.mock import MagicMock
from io import BytesIO

from app.services import storage


def _configure_r2(monkeypatch):
    monkeypatch.setenv("R2_ENABLED", "true")
    monkeypatch.setenv("R2_ACCOUNT_ID", "test-account")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("R2_BUCKET_NAME", "job-files")
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "https://files.example.com")


def test_r2_endpoint_is_derived_from_account_id(monkeypatch):
    _configure_r2(monkeypatch)
    assert storage._r2_endpoint() == "https://test-account.r2.cloudflarestorage.com"


def test_public_url_uses_configured_r2_domain(monkeypatch):
    _configure_r2(monkeypatch)
    assert (
        storage.public_url_for("job-portal/123/images/photo.png")
        == "https://files.example.com/job-portal/123/images/photo.png"
    )


def test_upload_bytes_puts_object_in_r2(monkeypatch):
    _configure_r2(monkeypatch)
    client = MagicMock()
    monkeypatch.setattr(storage, "_r2_client", lambda: client)

    result = storage.upload_bytes(
        b"hello",
        filename="document.txt",
        content_type="text/plain",
        folder="attachments",
        job_id="job-123",
    )

    assert result["storage"] == "r2"
    assert result["s3_path"].startswith("job-portal/job-123/attachments/")
    assert result["public_url"].startswith("https://files.example.com/")
    client.put_object.assert_called_once()
    call = client.put_object.call_args.kwargs
    assert call["Bucket"] == "job-files"
    assert call["Body"] == b"hello"
    assert call["ContentType"] == "text/plain"
    assert call["Metadata"] == {}


def test_read_public_object_only_reads_owned_r2_urls(monkeypatch):
    _configure_r2(monkeypatch)
    client = MagicMock()
    client.get_object.return_value = {
        "Body": BytesIO(b"image-bytes"),
        "ContentType": "image/png",
        "Metadata": {"watermark-version": "2"},
    }
    monkeypatch.setattr(storage, "_r2_client", lambda: client)

    result = storage.read_public_object(
        "https://files.example.com/job-portal/job-123/images/photo.png?v=2",
        max_bytes=1024,
    )

    assert result is not None
    assert result["data"] == b"image-bytes"
    assert result["metadata"] == {"watermark-version": "2"}
    client.get_object.assert_called_once_with(
        Bucket="job-files",
        Key="job-portal/job-123/images/photo.png",
    )
    assert (
        storage.read_public_object(
            "https://attacker.example/job-portal/job-123/images/photo.png",
            max_bytes=1024,
        )
        is None
    )
