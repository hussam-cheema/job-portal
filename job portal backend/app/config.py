from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


@lru_cache
def load_config() -> dict[str, Any]:
    path = ROOT_DIR / "config.yaml"
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


def cfg(*keys: str, default: Any = None) -> Any:
    data: Any = load_config()
    for key in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(key)
        if data is None:
            return default
    return data


def env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    return val.strip()


def site_url() -> str:
    return env("SITE_URL") or str(cfg("site", "url", default="http://localhost:3000"))


def site_name() -> str:
    return env("SITE_NAME") or str(cfg("site", "name", default="Pakistan Jobs Market"))


def watermark_text() -> str:
    return env("WATERMARK_TEXT") or str(cfg("watermark", "text") or site_url())


def watermark_opacity() -> float:
    raw = env("WATERMARK_OPACITY")
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    try:
        return float(cfg("watermark", "opacity", default=0.10))
    except (TypeError, ValueError):
        return 0.10


def r2_enabled() -> bool:
    flag = (env("R2_ENABLED") or "").lower()
    if flag in {"0", "false", "no"}:
        return False
    if flag in {"1", "true", "yes"}:
        return True
    return bool(cfg("r2", "enabled", default=True))


def jwt_secret() -> str:
    secret = env("JWT_SECRET")
    if not secret or len(secret) < 32:
        raise RuntimeError("JWT_SECRET must be configured with at least 32 characters")
    return secret


def admin_credentials() -> tuple[str, str]:
    """Admin credentials come from environment only (never config.yaml)."""
    user = env("ADMIN_USERNAME") or "admin"
    password = env("ADMIN_PASSWORD")
    if not password or not 12 <= len(password) <= 72:
        raise RuntimeError("ADMIN_PASSWORD must contain 12 to 72 characters")
    return user, password
