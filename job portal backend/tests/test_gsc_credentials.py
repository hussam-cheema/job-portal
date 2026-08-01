from __future__ import annotations

import json
import os

from google.oauth2 import service_account

os.environ["JOBPORTAL_TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite://"

from app.services.seo_tools import _build_gsc_credentials, gsc_credentials_configured


def test_gsc_credentials_support_serverless_json_secret(monkeypatch):
    credential_info = {
        "type": "service_account",
        "project_id": "job-portal",
        "private_key_id": "test-key",
        "private_key": "not-a-real-private-key",
        "client_email": "search-console@example.test",
        "client_id": "123",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    sentinel = object()
    captured: dict[str, object] = {}

    def fake_from_info(info, *, scopes):
        captured["info"] = info
        captured["scopes"] = scopes
        return sentinel

    monkeypatch.setenv("GSC_SERVICE_ACCOUNT_JSON", json.dumps(credential_info))
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_info",
        fake_from_info,
    )

    scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
    assert gsc_credentials_configured() is True
    assert _build_gsc_credentials(scopes) is sentinel
    assert captured == {"info": credential_info, "scopes": scopes}


def test_gsc_credentials_fall_back_to_mounted_file(monkeypatch, tmp_path):
    credentials_path = tmp_path / "service-account.json"
    credentials_path.write_text("{}", encoding="utf-8")
    sentinel = object()

    monkeypatch.delenv("GSC_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(credentials_path))
    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_file",
        lambda path, *, scopes: sentinel,
    )

    assert gsc_credentials_configured() is True
    assert _build_gsc_credentials(["scope"]) is sentinel
