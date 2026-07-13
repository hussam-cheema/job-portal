from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable

import httpx
import yaml
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = REPO_ROOT / "job portal backend"
FRONTEND_DIR = REPO_ROOT / "job portal frontend"

load_dotenv(BACKEND_DIR / ".env")
with (BACKEND_DIR / "config.yaml").open("r", encoding="utf-8") as config_file:
    CONFIG: dict[str, Any] = yaml.safe_load(config_file) or {}


class CheckFailed(RuntimeError):
    pass


def config(*keys: str, default: Any = None) -> Any:
    value: Any = CONFIG
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def require_env(name: str) -> str:
    value = env(name)
    if not value:
        raise CheckFailed(f"{name} is missing from {BACKEND_DIR / '.env'}")
    return value


def api_base() -> str:
    return (env("API_BASE_URL") or "http://localhost:8000").rstrip("/")


def site_base() -> str:
    return (env("SITE_URL") or str(config("site", "url", default="http://localhost:3000"))).rstrip("/")


def require_response(response: httpx.Response, label: str) -> httpx.Response:
    if response.is_success:
        return response
    detail = response.text.replace("\n", " ")[:500]
    raise CheckFailed(f"{label} returned HTTP {response.status_code}: {detail}")


def admin_headers(client: httpx.Client) -> dict[str, str]:
    response = client.post(
        f"{api_base()}/api/auth/login",
        json={"username": require_env("ADMIN_USERNAME"), "password": require_env("ADMIN_PASSWORD")},
    )
    require_response(response, "admin login")
    token = response.json().get("access_token")
    if not token:
        raise CheckFailed("admin login response did not include an access token")
    return {"Authorization": f"Bearer {token}"}


def add_backend_to_path() -> None:
    backend = str(BACKEND_DIR)
    if backend not in sys.path:
        sys.path.insert(0, backend)


def run(check: Callable[[], str | None]) -> int:
    try:
        summary = check()
        print(f"[PASS] {summary or 'check completed'}")
        return 0
    except KeyboardInterrupt:
        print("[FAIL] interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
