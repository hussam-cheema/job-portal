from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "migration"
    / "export_railway_env.py"
)
SPEC = importlib.util.spec_from_file_location("export_railway_env", MODULE_PATH)
assert SPEC and SPEC.loader
export_railway_env = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export_railway_env)


def test_api_export_replaces_azure_specific_database_and_mount_values():
    variables = {
        "POSTGRES_HOST": "private.azure.test",
        "POSTGRES_PASSWORD": "source-secret",
        "JWT_SECRET": "jwt-secret",
        "GOOGLE_APPLICATION_CREDENTIALS": "/secrets/gsc.json",
        "QWEN3_EMBEDDING_REQUIRE_PERSISTENT_STORAGE": "true",
        "AZURE_SUBSCRIPTION_ID": "subscription-id",
    }
    secrets = {"gsc-service-account-json": '{"type":"service_account"}'}

    result = export_railway_env.build_export("api", variables, secrets)

    assert "POSTGRES_HOST" not in result
    assert "POSTGRES_PASSWORD" not in result
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in result
    assert result["DATABASE_URL"] == "PASTE_NEON_POOLED_URL_HERE"
    assert result["JWT_SECRET"] == "jwt-secret"
    assert result["GSC_SERVICE_ACCOUNT_JSON"] == '{"type":"service_account"}'
    assert result["QWEN3_EMBEDDING_REQUIRE_PERSISTENT_STORAGE"] == "false"
    assert result["AZURE_COST_MANAGEMENT_ENABLED"] == "false"


def test_newsletter_export_contains_only_delivery_configuration():
    variables = {
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PASSWORD": "smtp-secret",
        "SITE_URL": "https://example.test",
        "JWT_SECRET": "not-required",
        "R2_ACCESS_KEY_ID": "not-required",
    }

    result = export_railway_env.build_export("newsletter", variables, {})

    assert result["SMTP_HOST"] == "smtp.example.test"
    assert result["SMTP_PASSWORD"] == "smtp-secret"
    assert result["DATABASE_URL"] == "PASTE_NEON_POOLED_URL_HERE"
    assert result["R2_LOGS_ENABLED"] == "false"
    assert "JWT_SECRET" not in result
    assert "R2_ACCESS_KEY_ID" not in result
