from __future__ import annotations

from unittest.mock import MagicMock
from io import BytesIO

from app.services import storage
from app.services import infrastructure


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


def test_delete_objects_only_removes_owned_r2_keys(monkeypatch):
    _configure_r2(monkeypatch)
    client = MagicMock()
    client.delete_objects.return_value = {}
    monkeypatch.setattr(storage, "_r2_client", lambda: client)

    assert storage.delete_objects(
        [
            "job-portal/job-123/attachments/file.txt",
            "job-portal/job-123/attachments/file.txt",
        ]
    ) == 1
    client.delete_objects.assert_called_once_with(
        Bucket="job-files",
        Delete={
            "Objects": [{"Key": "job-portal/job-123/attachments/file.txt"}],
            "Quiet": True,
        },
    )

    try:
        storage.delete_object("another-app/private.txt")
    except ValueError as exc:
        assert "Invalid R2 object key" in str(exc)
    else:
        raise AssertionError("Foreign object key should be rejected")


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


def test_r2_usage_sums_paginated_objects(monkeypatch):
    _configure_r2(monkeypatch)
    monkeypatch.setenv("R2_STORAGE_LIMIT_GB", "1")
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {"Contents": [{"Size": 100}, {"Size": 200}]},
        {"Contents": [{"Size": 300}]},
    ]
    client = MagicMock()
    client.get_paginator.return_value = paginator
    monkeypatch.setattr(storage, "_r2_client", lambda: client)
    infrastructure._r2_cache.clear()

    metric = infrastructure._r2_storage(force_refresh=True)

    assert metric.used_bytes == 600
    assert metric.total_bytes == 1024**3
    assert metric.object_count == 3
    assert metric.status == "healthy"
    paginator.paginate.assert_called_once_with(Bucket="job-files", Prefix="job-portal/")


def test_azure_costs_include_managed_group_and_invoice_vnet_meter(monkeypatch):
    monkeypatch.setenv("AZURE_COST_MANAGEMENT_ENABLED", "true")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "subscription-1")
    monkeypatch.setenv("AZURE_RESOURCE_GROUP", "job-portal-prod-rg")
    monkeypatch.setenv(
        "AZURE_MANAGED_RESOURCE_GROUP",
        "ME_job-portal-prod-env_job-portal-prod-rg_centralindia",
    )
    monkeypatch.setattr(infrastructure, "_azure_access_token", lambda: "token")
    infrastructure._azure_cost_cache.clear()
    requested_urls: list[str] = []

    class Response:
        def __init__(self, rows):
            self._rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "properties": {
                    "columns": [
                        {"name": "PreTaxCost"},
                        {"name": "ResourceId"},
                        {"name": "ResourceType"},
                        {"name": "MeterCategory"},
                        {"name": "MeterSubCategory"},
                        {"name": "Currency"},
                    ],
                    "rows": self._rows,
                }
            }

    def fake_post(url: str, **_kwargs):
        requested_urls.append(url)
        if "/resourceGroups/job-portal-prod-rg/" in url:
            return Response(
                [
                    [
                        3.93648,
                        "/subscriptions/subscription-1/resourceGroups/job-portal-prod-rg/"
                        "providers/microsoft.app/containerapps/job-portal-api",
                        "microsoft.app/containerapps",
                        "Azure Container Apps",
                        "Azure Container Apps",
                        "USD",
                    ]
                ]
            )
        return Response(
            [
                [
                    1.510051,
                    "/subscriptions/subscription-1/resourceGroups/"
                    "ME_job-portal-prod-env_job-portal-prod-rg_centralindia/"
                    "providers/microsoft.network/publicipaddresses/capp-svc-lb-ip",
                    "microsoft.network/publicipaddresses",
                    "Virtual Network",
                    "IP Addresses",
                    "USD",
                ]
            ]
        )

    monkeypatch.setattr(infrastructure.httpx, "post", fake_post)

    costs = infrastructure._azure_month_to_date_costs(force_refresh=True)

    assert costs is not None
    assert costs["category_costs"]["backend"] == 3.9365
    assert costs["category_costs"]["vnet"] == 1.5101
    assert "public_ip" not in costs["category_costs"]
    assert len(requested_urls) == 2
    assert any("ME_job-portal-prod-env" in url for url in requested_urls)
