#!/usr/bin/env python3
"""Export Azure Container App configuration for Railway's JSON Raw Editor.

Secret values are written only to stdout. Pipe stdout directly to the system
clipboard; never redirect it into the repository or commit the output.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any


DATABASE_PARTS = {
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "DB_POOL_TIMEOUT",
    "DB_POOL_RECYCLE",
}

API_EXCLUSIONS = DATABASE_PARTS | {
    "GOOGLE_APPLICATION_CREDENTIALS",
    "BACKEND_CPU_LIMIT_CORES",
    "BACKEND_MEMORY_LIMIT_MB",
    "EMBEDDINGGEMMA_MODEL_PATH",
    "EMBEDDINGGEMMA_MODEL_MOUNT_PATH",
    "EMBEDDINGGEMMA_REQUIRE_PERSISTENT_STORAGE",
    "EMBEDDINGGEMMA_THREADS",
}

NEWSLETTER_KEYS = {
    "ADMIN_RECOVERY_EMAIL",
    "LOG_LEVEL",
    "PUBLIC_API_URL",
    "SITE_URL",
    "SMTP_AUTH",
    "SMTP_FROM_EMAIL",
    "SMTP_HOST",
    "SMTP_PASSWORD",
    "SMTP_PORT",
    "SMTP_SEND_ATTEMPTS",
    "SMTP_STARTTLS",
    "SMTP_TIMEOUT_SECONDS",
    "SMTP_USERNAME",
    "SMTP_USE_SSL",
    "NEWSLETTER_MAX_DELIVERY_ATTEMPTS",
    "EMAIL_DELIVERY_PROVIDER",
    "EMAIL_FROM_EMAIL",
    "RESEND_API_KEY",
    "RESEND_API_URL",
    "EMAIL_HTTP_TIMEOUT_SECONDS",
}

API_OVERRIDES = {
    "DATABASE_URL": "PASTE_NEON_POOLED_URL_HERE",
    "DB_POOL_MODE": "serverless",
    "DB_SSLMODE": "require",
    "SEED_ON_STARTUP": "false",
    "RESET_DB_SCHEMA": "false",
    "NEWSLETTER_RETRY_ENABLED": "false",
    "WRITE_FREEZE_ENABLED": "true",
    "BACKEND_PROVIDER": "Railway Serverless",
    "BACKEND_RUNTIME_MODEL": "Serverless",
    "DATABASE_PROVIDER": "Neon Postgres",
    "DB_STORAGE_LIMIT_GB": "0.5",
    "BACKEND_MIN_REPLICAS": "0",
    "BACKEND_MAX_REPLICAS": "1",
    "RAILWAY_PLAN": "Hobby",
    "RAILWAY_MONTHLY_COST_USD": "5",
    "NEON_PLAN": "Free",
    "NEON_MONTHLY_COST_USD": "0",
    "INFRA_CURRENT_STACK_STARTED_MONTH": "2026-08",
    "INFRA_COST_HISTORY_MONTHS": "12",
    "QWEN3_EMBEDDING_MODEL_PATH": "/models/Qwen3-Embedding-0.6B-Q8_0.gguf",
    "QWEN3_EMBEDDING_MODEL_MOUNT_PATH": "/models",
    "QWEN3_EMBEDDING_REQUIRE_PERSISTENT_STORAGE": "false",
    "QWEN3_EMBEDDING_CACHE_BACKGROUND": "true",
    "QWEN3_EMBEDDING_THREADS": "1",
    # Railway has no Azure managed identity. Cost telemetry can be re-enabled
    # later with a least-privilege Azure service principal.
    "AZURE_COST_MANAGEMENT_ENABLED": "false",
}

NEWSLETTER_OVERRIDES = {
    "DATABASE_URL": "PASTE_NEON_POOLED_URL_HERE",
    "DB_POOL_MODE": "serverless",
    "DB_SSLMODE": "require",
    "SEED_ON_STARTUP": "false",
    "RESET_DB_SCHEMA": "false",
    "NEWSLETTER_RETRY_ENABLED": "false",
    "R2_LOGS_ENABLED": "false",
    "APP_ENV": "production",
}

# The migration service is intentionally configured separately from the API
# and cron services. After cutover, set MIGRATION_MODE=backup and point
# BACKUP_DATABASE_URL at the Neon direct (non-pooler) URL to create an
# independent, checksum-verified R2 backup before deleting Azure PostgreSQL.


def _az_json(arguments: list[str]) -> Any:
    completed = subprocess.run(
        ["az", *arguments, "-o", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _resolved_azure_variables(
    *,
    resource_group: str,
    container_app: str,
) -> tuple[dict[str, str], dict[str, str]]:
    app = _az_json(
        [
            "containerapp",
            "show",
            "--resource-group",
            resource_group,
            "--name",
            container_app,
        ]
    )
    secret_rows = _az_json(
        [
            "containerapp",
            "secret",
            "list",
            "--resource-group",
            resource_group,
            "--name",
            container_app,
            "--show-values",
        ]
    )
    secrets = {
        str(row["name"]): str(row["value"])
        for row in secret_rows
        if row.get("name") and row.get("value") is not None
    }

    containers = (
        app.get("properties", {}).get("template", {}).get("containers", [])
    )
    if not containers:
        raise RuntimeError("Azure Container App has no configured container")

    variables: dict[str, str] = {}
    for row in containers[0].get("env", []):
        name = row.get("name")
        if not name:
            continue
        secret_ref = row.get("secretRef")
        if secret_ref:
            if secret_ref not in secrets:
                raise RuntimeError(f"Azure secret {secret_ref!r} is unavailable")
            variables[str(name)] = secrets[secret_ref]
        elif row.get("value") is not None:
            variables[str(name)] = str(row["value"])
    return variables, secrets


def build_export(
    service: str,
    variables: dict[str, str],
    secrets: dict[str, str],
) -> dict[str, str]:
    if service == "api":
        exported = {
            name: value
            for name, value in variables.items()
            if name not in API_EXCLUSIONS
        }
        gsc_json = secrets.get("gsc-service-account-json")
        if gsc_json:
            exported["GSC_SERVICE_ACCOUNT_JSON"] = gsc_json
        exported.update(API_OVERRIDES)
        return dict(sorted(exported.items()))

    exported = {
        name: value for name, value in variables.items() if name in NEWSLETTER_KEYS
    }
    exported.update(NEWSLETTER_OVERRIDES)
    return dict(sorted(exported.items()))


def render_json(exported: dict[str, str]) -> str:
    """Render the complete object accepted by Railway's JSON Raw Editor."""
    return json.dumps(exported, ensure_ascii=True, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", choices=("api", "newsletter"), required=True)
    parser.add_argument("--resource-group", default="job-portal-prod-rg")
    parser.add_argument("--container-app", default="job-portal-api")
    parser.add_argument(
        "--copy",
        action="store_true",
        help="copy the complete JSON object to the macOS clipboard",
    )
    args = parser.parse_args()

    variables, secrets = _resolved_azure_variables(
        resource_group=args.resource_group,
        container_app=args.container_app,
    )
    exported = build_export(args.service, variables, secrets)
    payload = render_json(exported)
    if args.copy:
        subprocess.run(
            ["pbcopy"],
            input=payload,
            check=True,
            text=True,
        )
        print(
            f"Copied {len(exported)} {args.service} variables as JSON. "
            "The clipboard now contains production secrets; overwrite it after pasting.",
            file=sys.stderr,
        )
    else:
        print(
            "WARNING: stdout contains production secrets; do not save or share it.",
            file=sys.stderr,
        )
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
