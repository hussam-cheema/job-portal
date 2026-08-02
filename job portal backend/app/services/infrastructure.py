from __future__ import annotations

import json
import math
import os
import resource
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import cfg, env, r2_enabled
from app.logging_config import get_logger
from app.models import InfrastructureCostSnapshot
from app.schemas import (
    InfrastructureAlert,
    InfrastructureComputeMetric,
    InfrastructureConnectionMetric,
    InfrastructureCostHistoryPoint,
    InfrastructureCostItem,
    InfrastructureCostSummary,
    InfrastructureDashboard,
    InfrastructureQuotaMetric,
    InfrastructureStorageMetric,
)
from app.services import storage

logger = get_logger("jobportal.infrastructure")

GIB = 1024**3
MIB = 1024**2
_PROCESS_STARTED = time.monotonic()
_cpu_lock = threading.Lock()
_cpu_previous = (time.monotonic(), time.process_time())
_r2_cache_lock = threading.Lock()
_r2_cache: dict[str, Any] = {}
_R2_CACHE_SECONDS = 300
_azure_cost_cache_lock = threading.Lock()
_azure_cost_cache: dict[str, Any] = {}
_AZURE_COST_CACHE_SECONDS = 900


def _env_float(name: str, default: float | None = None) -> float | None:
    raw = env(name)
    if raw is None:
        return default
    try:
        value = float(raw)
        return value if math.isfinite(value) and value >= 0 else default
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = env(name)
    if raw is None:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _percent(used: float | int | None, total: float | int | None) -> float | None:
    if used is None or total is None or total <= 0:
        return None
    return round(max(0.0, (float(used) / float(total)) * 100), 1)


def _status(percent: float | None, *, available: bool = True) -> str:
    if not available:
        return "unavailable"
    if percent is None:
        return "unknown"
    if percent >= 90:
        return "critical"
    if percent >= 75:
        return "warning"
    return "healthy"


def _read_number(path: str) -> int | None:
    try:
        value = Path(path).read_text(encoding="utf-8").strip()
        if value == "max":
            return None
        return int(value)
    except (OSError, ValueError):
        return None


def _cgroup_cpu_limit() -> float | None:
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text(encoding="utf-8").split()
        if quota != "max" and int(period) > 0:
            return int(quota) / int(period)
    except (OSError, ValueError):
        pass
    quota = _read_number("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
    period = _read_number("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
    if quota and quota > 0 and period and period > 0:
        return quota / period
    return None


def _cgroup_memory_limit() -> int | None:
    limit = _read_number("/sys/fs/cgroup/memory.max")
    if limit is None:
        limit = _read_number("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    # Some runtimes expose a very large sentinel instead of an actual limit.
    if limit and limit < 1 << 60:
        return limit
    return None


def _memory_used() -> int | None:
    current = _read_number("/sys/fs/cgroup/memory.current")
    if current is None:
        current = _read_number("/sys/fs/cgroup/memory/memory.usage_in_bytes")
    if current is not None:
        return current
    try:
        resident_pages = int(Path("/proc/self/statm").read_text(encoding="utf-8").split()[1])
        return resident_pages * int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError, IndexError):
        try:
            maximum = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return int(maximum if sys.platform == "darwin" else maximum * 1024)
        except (OSError, ValueError):
            return None


def _cpu_used_percent(allocated_cores: float) -> float:
    global _cpu_previous
    now = (time.monotonic(), time.process_time())
    with _cpu_lock:
        previous = _cpu_previous
        _cpu_previous = now
    elapsed = max(0.001, now[0] - previous[0])
    cpu_elapsed = max(0.0, now[1] - previous[1])
    return round(min(100.0, (cpu_elapsed / elapsed / max(allocated_cores, 0.001)) * 100), 1)


def _r2_storage(force_refresh: bool) -> InfrastructureStorageMetric:
    total_bytes = int((_env_float("R2_STORAGE_LIMIT_GB", 10.0) or 0) * GIB) or None
    bucket = storage._bucket()
    prefix_root = str(cfg("r2", "prefix", default="job-portal")).strip("/")
    prefix = f"{prefix_root}/" if prefix_root else ""
    configured = bool(
        r2_enabled()
        and bucket
        and env("R2_ACCESS_KEY_ID")
        and env("R2_SECRET_ACCESS_KEY")
    )
    if not configured:
        return InfrastructureStorageMetric(
            id="r2",
            name="Object storage",
            provider="Cloudflare R2",
            total_bytes=total_bytes,
            status="unavailable",
            source="configuration",
            detail="R2 is disabled or its bucket credentials are not configured.",
        )

    cache_key = f"{bucket}:{prefix}"
    with _r2_cache_lock:
        cached = _r2_cache.get(cache_key)
        if cached and not force_refresh and time.monotonic() - cached["at"] < _R2_CACHE_SECONDS:
            used_bytes, object_count = cached["used_bytes"], cached["object_count"]
        else:
            used_bytes = object_count = None

    if used_bytes is None:
        try:
            client = storage._r2_client()
            paginator = client.get_paginator("list_objects_v2")
            used_bytes = 0
            object_count = 0
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                objects = page.get("Contents", [])
                used_bytes += sum(int(item.get("Size", 0) or 0) for item in objects)
                object_count += len(objects)
            with _r2_cache_lock:
                _r2_cache[cache_key] = {
                    "at": time.monotonic(),
                    "used_bytes": used_bytes,
                    "object_count": object_count,
                }
        except Exception:
            logger.exception("R2 usage collection failed bucket=%s", bucket)
            return InfrastructureStorageMetric(
                id="r2",
                name="Object storage",
                provider="Cloudflare R2",
                total_bytes=total_bytes,
                status="unavailable",
                source="R2 S3 API",
                detail="Live bucket usage could not be collected. The next refresh will retry.",
            )

    utilization = _percent(used_bytes, total_bytes)
    return InfrastructureStorageMetric(
        id="r2",
        name="Object storage",
        provider="Cloudflare R2",
        used_bytes=used_bytes,
        total_bytes=total_bytes,
        utilization_percent=utilization,
        object_count=object_count,
        status=_status(utilization),
        source="R2 S3 API (cached up to 5 min)",
        detail="The total is the configured storage budget; R2 itself has elastic capacity.",
    )


def _database_storage(db: Session) -> InfrastructureStorageMetric:
    total_bytes = int((_env_float("DB_STORAGE_LIMIT_GB", 32.0) or 0) * GIB) or None
    database_provider = env("DATABASE_PROVIDER", "Azure PostgreSQL") or "Azure PostgreSQL"
    try:
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            used_bytes = int(db.execute(text("SELECT pg_database_size(current_database())")).scalar_one())
            source = "PostgreSQL pg_database_size"
        elif dialect == "sqlite":
            page_count = int(db.execute(text("PRAGMA page_count")).scalar_one())
            page_size = int(db.execute(text("PRAGMA page_size")).scalar_one())
            used_bytes = page_count * page_size
            source = "SQLite page usage (test environment)"
        else:
            raise RuntimeError(f"Unsupported database dialect: {dialect}")
        utilization = _percent(used_bytes, total_bytes)
        return InfrastructureStorageMetric(
            id="database",
            name="Database storage",
            provider=database_provider if dialect == "postgresql" else "Local database",
            used_bytes=used_bytes,
            total_bytes=total_bytes,
            utilization_percent=utilization,
            status=_status(utilization),
            source=source,
            detail="Live database size against the provisioned server storage allocation.",
        )
    except Exception:
        logger.exception("database usage collection failed")
        return InfrastructureStorageMetric(
            id="database",
            name="Database storage",
            provider=database_provider,
            total_bytes=total_bytes,
            status="unavailable",
            source="database",
            detail="Database size could not be collected. The next refresh will retry.",
        )


def _database_connections(db: Session) -> InfrastructureConnectionMetric:
    try:
        pool = db.get_bind().pool
        size = getattr(pool, "size", None)
        checked_out = getattr(pool, "checkedout", None)
        if not callable(size) or not callable(checked_out):
            raise RuntimeError("Connection pool does not expose counters")
        base_size = int(size())
        configured_overflow = _env_int("DB_MAX_OVERFLOW", 5)
        used = int(checked_out())
        total = base_size + configured_overflow
        utilization = _percent(used, total)
        return InfrastructureConnectionMetric(
            used=used,
            total=total,
            utilization_percent=utilization,
            status=_status(utilization),
            detail="SQLAlchemy checked-out connections against pool plus overflow capacity.",
        )
    except Exception:
        return InfrastructureConnectionMetric(
            status="unknown",
            detail="Connection counters are unavailable for this database pool.",
        )


def _compute_metrics() -> list[InfrastructureComputeMetric]:
    backend_provider = env("BACKEND_PROVIDER", "Azure Container Apps") or "Azure Container Apps"
    backend_runtime = (
        env("BACKEND_RUNTIME_MODEL", "Dedicated per replica")
        or "Dedicated per replica"
    )
    cpu_allocation = _cgroup_cpu_limit() or _env_float("BACKEND_CPU_LIMIT_CORES", 0.5) or 0.5
    memory_allocation = _cgroup_memory_limit()
    if memory_allocation is None:
        memory_allocation = int((_env_float("BACKEND_MEMORY_LIMIT_MB", 1024.0) or 1024.0) * MIB)
    memory_used = _memory_used()
    memory_percent = _percent(memory_used, memory_allocation)
    cpu_percent = _cpu_used_percent(cpu_allocation)
    backend_status = _status(max(cpu_percent, memory_percent or 0.0))

    return [
        InfrastructureComputeMetric(
            id="backend",
            name="Backend API",
            provider=backend_provider,
            runtime_model=backend_runtime,
            cpu_used_percent=cpu_percent,
            cpu_allocated_cores=round(cpu_allocation, 2),
            memory_used_bytes=memory_used,
            memory_allocated_bytes=memory_allocation,
            memory_used_percent=memory_percent,
            min_replicas=_env_int("BACKEND_MIN_REPLICAS", 0),
            max_replicas=_env_int("BACKEND_MAX_REPLICAS", 2),
            uptime_seconds=int(time.monotonic() - _PROCESS_STARTED),
            status=backend_status,
            detail="Usage is for the responding replica; allocation is detected from cgroups or deployment settings.",
        )
    ]


def _quota_metrics() -> list[InfrastructureQuotaMetric]:
    plan = env("FRONTEND_PLAN", "Free") or "Free"
    app_limit_mb = _env_float("FRONTEND_APP_LIMIT_MB", 250.0) or 250.0
    bandwidth_limit_gb = _env_float("FRONTEND_BANDWIDTH_LIMIT_GB", 100.0) or 100.0
    return [
        InfrastructureQuotaMetric(
            id="frontend_assets",
            name="Frontend app size",
            provider=f"Azure Static Web Apps {plan}",
            total=app_limit_mb,
            unit="MB",
            status="unknown",
            detail="Provider quota; deployed artifact usage is not exposed to the backend.",
        ),
        InfrastructureQuotaMetric(
            id="frontend_bandwidth",
            name="Frontend bandwidth",
            provider=f"Azure Static Web Apps {plan}",
            total=bandwidth_limit_gb,
            unit="GB/month",
            status="unknown",
            detail="Included plan bandwidth; live tenant usage requires Azure Cost Management or Monitor access.",
        ),
    ]


def _bool_env(name: str, default: bool = False) -> bool:
    fallback = "true" if default else "false"
    return (env(name, fallback) or fallback).lower() in {"1", "true", "yes", "on"}


def _azure_access_token() -> str | None:
    endpoint = env("IDENTITY_ENDPOINT")
    identity_header = env("IDENTITY_HEADER")
    if endpoint and identity_header:
        response = httpx.get(
            endpoint,
            params={
                "resource": "https://management.azure.com/",
                "api-version": "2019-08-01",
            },
            headers={"X-IDENTITY-HEADER": identity_header},
            timeout=8.0,
        )
        response.raise_for_status()
        return str(response.json().get("access_token") or "") or None

    tenant_id = env("AZURE_TENANT_ID")
    client_id = env("AZURE_CLIENT_ID")
    client_secret = env("AZURE_CLIENT_SECRET")
    if tenant_id and client_id and client_secret:
        response = httpx.post(
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://management.azure.com/.default",
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return str(response.json().get("access_token") or "") or None
    return None


def _azure_cost_category(
    resource_type: str,
    resource_id: str,
    meter_category: str = "",
    meter_subcategory: str = "",
) -> str:
    value = f"{resource_type} {resource_id}".casefold()
    meter = f"{meter_category} {meter_subcategory}".casefold()
    if "microsoft.app/containerapps" in value:
        return "backend"
    if "microsoft.app/managedenvironments" in value:
        return "container_environment"
    if "microsoft.web/staticsites" in value:
        return "frontend"
    if "microsoft.dbforpostgresql/flexibleservers" in value:
        return "database"
    # Azure bills the Container Apps environment public IP under the
    # "Virtual Network / IP Addresses" meter even though the resource type is
    # Microsoft.Network/publicIPAddresses. Prefer the invoice meter here so
    # the VNet total agrees with Azure Cost Management.
    if "virtual network" in meter:
        return "vnet"
    if "microsoft.network/virtualnetworks" in value:
        return "vnet"
    if "microsoft.network/loadbalancers" in value:
        return "load_balancer"
    if "microsoft.network/publicipaddresses" in value:
        return "public_ip"
    if "microsoft.storage/storageaccounts" in value or "fileservices" in value:
        return "azure_files"
    if "microsoft.operationalinsights/workspaces" in value:
        return "log_analytics"
    if "microsoft.network/privatednszones" in value:
        return "private_dns"
    return "azure_other"


def _azure_cost_scopes(subscription_id: str) -> list[str]:
    base = f"/subscriptions/{subscription_id}"
    resource_groups = [
        env("AZURE_RESOURCE_GROUP"),
        env("AZURE_MANAGED_RESOURCE_GROUP"),
    ]
    scopes: list[str] = []
    seen: set[str] = set()
    for raw_group in resource_groups:
        group = (raw_group or "").strip()
        key = group.casefold()
        if not group or key in seen:
            continue
        seen.add(key)
        scopes.append(f"{base}/resourceGroups/{group}")
    return scopes or [base]


def _query_azure_cost_scope(scope: str, token: str) -> dict[str, Any]:
    response = httpx.post(
        "https://management.azure.com"
        f"{scope}/providers/Microsoft.CostManagement/query"
        "?api-version=2023-11-01",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "type": "ActualCost",
            "timeframe": "MonthToDate",
            "dataset": {
                "granularity": "None",
                "aggregation": {
                    "totalCost": {"name": "PreTaxCost", "function": "Sum"}
                },
                "grouping": [
                    {"type": "Dimension", "name": "ResourceId"},
                    {"type": "Dimension", "name": "ResourceType"},
                    {"type": "Dimension", "name": "MeterCategory"},
                    {"type": "Dimension", "name": "MeterSubCategory"},
                ],
            },
        },
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()


def _azure_month_to_date_costs(force_refresh: bool) -> dict[str, Any] | None:
    if not _bool_env("AZURE_COST_MANAGEMENT_ENABLED"):
        return None
    subscription_id = env("AZURE_SUBSCRIPTION_ID")
    if not subscription_id:
        return None
    scopes = _azure_cost_scopes(subscription_id)
    cache_key = "|".join(scopes)
    with _azure_cost_cache_lock:
        cached = _azure_cost_cache.get(cache_key)
        if (
            cached
            and not force_refresh
            and time.monotonic() - cached["at"] < _AZURE_COST_CACHE_SECONDS
        ):
            return dict(cached["value"])

    try:
        token = _azure_access_token()
        if not token:
            raise RuntimeError(
                "No managed identity or Azure service-principal credential is available"
            )
        category_costs: dict[str, float] = {}
        resource_ids: dict[str, list[str]] = {}
        currency = "USD"
        for scope in scopes:
            properties = (_query_azure_cost_scope(scope, token).get("properties") or {})
            columns = [
                str(column.get("name") or "")
                for column in properties.get("columns") or []
            ]
            indexes = {name.casefold(): index for index, name in enumerate(columns)}
            cost_index = indexes.get("pretaxcost", indexes.get("cost", 0))
            resource_id_index = indexes.get("resourceid")
            resource_type_index = indexes.get("resourcetype")
            meter_category_index = indexes.get("metercategory")
            meter_subcategory_index = indexes.get("metersubcategory")
            currency_index = indexes.get("currency")
            for raw_row in properties.get("rows") or []:
                if not isinstance(raw_row, list):
                    continue
                try:
                    cost = float(raw_row[cost_index])
                except (IndexError, TypeError, ValueError):
                    continue

                def row_value(index: int | None) -> str:
                    return (
                        str(raw_row[index] or "")
                        if index is not None and index < len(raw_row)
                        else ""
                    )

                resource_id = row_value(resource_id_index)
                category = _azure_cost_category(
                    row_value(resource_type_index),
                    resource_id,
                    row_value(meter_category_index),
                    row_value(meter_subcategory_index),
                )
                category_costs[category] = category_costs.get(category, 0.0) + cost
                if resource_id:
                    ids = resource_ids.setdefault(category, [])
                    if resource_id not in ids:
                        ids.append(resource_id)
                if currency_index is not None:
                    currency = row_value(currency_index) or currency
        value = {
            "category_costs": {
                key: round(amount, 4) for key, amount in category_costs.items()
            },
            "resource_ids": resource_ids,
            "currency": currency,
            "scope": ", ".join(scopes),
        }
        with _azure_cost_cache_lock:
            _azure_cost_cache[cache_key] = {"at": time.monotonic(), "value": value}
        return value
    except Exception:
        logger.exception("Azure Cost Management collection failed scopes=%s", scopes)
        return None


def _month_key(month_offset: int = 0) -> str:
    now = datetime.now(timezone.utc)
    month_index = now.year * 12 + now.month - 1 + month_offset
    year, zero_based_month = divmod(month_index, 12)
    return f"{year:04d}-{zero_based_month + 1:02d}"


def _manual_cost_history() -> dict[str, dict[str, Any]]:
    """Parse optional invoice backfill without making the dashboard depend on it.

    Supported shape:
      [{"month":"2026-07","provider_costs":{"Railway":5,"Neon":0},"paid_usd":5}]
    or:
      {"2026-07":{"provider_costs":{"Railway":5,"Neon":0},"paid_usd":5}}

    The original shorthand remains supported:
      {"2026-07":{"Railway":5,"Neon":0}}
    """
    raw = env("INFRA_COST_HISTORY_JSON")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        entries = (
            parsed.items()
            if isinstance(parsed, dict)
            else (
                (str(item.get("month") or ""), item)
                for item in parsed
                if isinstance(item, dict)
            )
        )
        result: dict[str, dict[str, Any]] = {}
        for month, raw_entry in entries:
            if not isinstance(raw_entry, dict):
                continue
            provider_values = raw_entry.get("provider_costs", raw_entry)
            if (
                len(month) != 7
                or month[4] != "-"
                or not isinstance(provider_values, dict)
            ):
                continue
            clean: dict[str, float] = {}
            for provider, raw_value in provider_values.items():
                if provider in {"paid_usd", "provider_costs"}:
                    continue
                try:
                    value = float(raw_value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value) and value >= 0:
                    clean[str(provider)] = round(value, 2)
            if clean:
                try:
                    paid = float(raw_entry.get("paid_usd", 0) or 0)
                except (TypeError, ValueError):
                    paid = 0.0
                result[month] = {
                    "provider_costs": clean,
                    "paid_usd": round(paid, 2)
                    if math.isfinite(paid) and paid >= 0
                    else 0.0,
                }
        return result
    except (TypeError, ValueError, json.JSONDecodeError):
        logger.warning("INFRA_COST_HISTORY_JSON is invalid and was ignored")
        return {}


def _cost_history(
    db: Session,
    *,
    current_provider_costs: dict[str, float],
    current_estimated: bool,
    current_paid_usd: float,
) -> list[InfrastructureCostHistoryPoint]:
    history_months = min(36, max(2, _env_int("INFRA_COST_HISTORY_MONTHS", 12)))
    months = [_month_key(offset) for offset in range(-(history_months - 1), 1)]
    current_month = months[-1]

    try:
        changed = False
        for provider, cost in current_provider_costs.items():
            row = db.execute(
                select(InfrastructureCostSnapshot).where(
                    InfrastructureCostSnapshot.month == current_month,
                    InfrastructureCostSnapshot.provider == provider,
                )
            ).scalar_one_or_none()
            if row is None:
                db.add(
                    InfrastructureCostSnapshot(
                        id=str(uuid4()),
                        month=current_month,
                        provider=provider,
                        cost_usd=cost,
                        source="dashboard snapshot",
                        estimated=current_estimated,
                        captured_at=datetime.utcnow(),
                    )
                )
                changed = True
            elif (
                round(row.cost_usd, 2) != round(cost, 2)
                or row.estimated != current_estimated
            ):
                row.cost_usd = cost
                row.estimated = current_estimated
                row.source = "dashboard snapshot"
                row.updated_at = datetime.utcnow()
                changed = True
        if changed:
            db.commit()

        rows = (
            db.execute(
                select(InfrastructureCostSnapshot).where(
                    InfrastructureCostSnapshot.month.in_(months)
                )
            )
            .scalars()
            .all()
        )
    except Exception:
        db.rollback()
        logger.exception("infrastructure cost snapshot persistence failed")
        rows = []

    by_month: dict[str, dict[str, float]] = {}
    estimated_by_month: dict[str, bool] = {}
    for row in rows:
        by_month.setdefault(row.month, {})[row.provider] = round(row.cost_usd, 2)
        estimated_by_month[row.month] = estimated_by_month.get(row.month, False) or bool(
            row.estimated
        )

    manual = _manual_cost_history()
    for month, entry in manual.items():
        if month in months:
            by_month[month] = entry["provider_costs"]
            estimated_by_month[month] = False

    # Railway and Neon did not exist before cutover. That fact does not imply
    # the retired Azure stack cost $0, so an unbackfilled month is deliberately
    # marked unavailable instead of presenting a misleading zero total.
    stack_started = env("INFRA_CURRENT_STACK_STARTED_MONTH", current_month) or current_month
    points: list[InfrastructureCostHistoryPoint] = []
    for month in months:
        values = by_month.get(month)
        if values is None and month < stack_started:
            values = {"Railway": 0.0, "Neon": 0.0}
            source = "pre-cutover provider baseline; Azure invoice not backfilled"
            estimated = True
            available = False
        elif values is None:
            values = {}
            source = "not yet captured"
            estimated = True
            available = False
        else:
            source = "manual invoice backfill" if month in manual else "stored monthly snapshot"
            estimated = estimated_by_month.get(month, True)
            available = True
        total = round(sum(values.values()), 2) if available else None
        configured_paid = (
            float(manual[month].get("paid_usd", 0.0))
            if month in manual
            else (current_paid_usd if month == current_month else 0.0)
        )
        paid = round(min(total or 0.0, max(0.0, configured_paid)), 2)
        outstanding = round(max(0.0, (total or 0.0) - paid), 2) if available else None
        points.append(
            InfrastructureCostHistoryPoint(
                month=month,
                total_usd=total,
                paid_usd=paid,
                outstanding_usd=outstanding,
                provider_costs=values,
                source=source,
                estimated=estimated,
                available=available,
            )
        )
    return points


def _cost_summary(
    db: Session,
    r2_metric: InfrastructureStorageMetric,
    *,
    force_refresh: bool,
) -> InfrastructureCostSummary:
    # Cloudflare R2 Standard pricing, last verified 2026-07: first 10 GB-month free,
    # then USD 0.015/GB-month. This snapshot is directional, not an invoice.
    r2_gb = (r2_metric.used_bytes or 0) / GIB
    r2_billable_gb = math.ceil(max(0.0, r2_gb - 10.0))
    r2_estimate = round(r2_billable_gb * 0.015, 2)

    railway_plan = env("RAILWAY_PLAN", "Hobby") or "Hobby"
    railway_actual = _env_float("RAILWAY_MONTH_TO_DATE_COST_USD")
    railway_estimate = _env_float("RAILWAY_MONTHLY_COST_USD")
    if railway_estimate is None and railway_plan.casefold() == "hobby":
        # Railway Hobby has a $5 minimum usage commitment that includes the
        # first $5 of resource usage.
        railway_estimate = 5.0
    railway_cost = railway_actual if railway_actual is not None else railway_estimate

    neon_plan = env("NEON_PLAN", "Free") or "Free"
    neon_actual = _env_float("NEON_MONTH_TO_DATE_COST_USD")
    neon_estimate = _env_float("NEON_MONTHLY_COST_USD")
    if neon_estimate is None and neon_plan.casefold() == "free":
        neon_estimate = 0.0
    neon_cost = neon_actual if neon_actual is not None else neon_estimate

    frontend_plan = (env("FRONTEND_PLAN", "Free") or "Free").lower()
    frontend_estimate = (
        _env_float("FRONTEND_MONTHLY_COST_USD")
        if env("FRONTEND_MONTHLY_COST_USD") is not None
        else (0.0 if frontend_plan == "free" else None)
    )
    azure_live = _azure_month_to_date_costs(force_refresh)
    frontend_cost = (
        float((azure_live.get("category_costs") or {}).get("frontend", 0.0))
        if azure_live
        else frontend_estimate
    )
    # The service list intentionally contains only the retained Static Web App.
    # However, resources retired during this billing month can still leave
    # legitimate accrued charges. Preserve those charges in the provider total
    # so removing an unused service never makes the amount owed disappear.
    azure_current_total = (
        round(
            sum(
                float(value)
                for value in (azure_live.get("category_costs") or {}).values()
            ),
            2,
        )
        if azure_live
        else frontend_cost
    )
    resources = (azure_live or {}).get("resource_ids") or {}
    has_actual = any(
        value is not None for value in (railway_actual, neon_actual)
    ) or azure_live is not None
    basis = "provider_actuals_and_estimates" if has_actual else "monthly_estimate"

    items = [
        InfrastructureCostItem(
            id="r2",
            name="Object storage",
            provider="Cloudflare R2 Standard",
            monthly_estimate_usd=r2_estimate,
            configured=True,
            detail="Snapshot estimate: first 10 GB-month free, then $0.015 per GB-month; operations are separate.",
        ),
        InfrastructureCostItem(
            id="railway",
            name="Backend API + newsletter retry",
            provider=f"Railway {railway_plan}",
            monthly_estimate_usd=railway_cost,
            configured=railway_cost is not None,
            detail=(
                "Live month-to-date Railway cost supplied by configuration."
                if railway_actual is not None
                else "Railway plan estimate. Set RAILWAY_MONTH_TO_DATE_COST_USD to mirror the billing dashboard."
            ),
        ),
        InfrastructureCostItem(
            id="neon",
            name="PostgreSQL database",
            provider=f"Neon {neon_plan}",
            monthly_estimate_usd=neon_cost,
            configured=neon_cost is not None,
            detail=(
                "Live month-to-date Neon cost supplied by configuration."
                if neon_actual is not None
                else "Neon plan estimate. Free projects do not expose the paid Consumption API."
            ),
        ),
        InfrastructureCostItem(
            id="azure_static_web_apps",
            name="Frontend hosting",
            provider=f"Azure Static Web Apps {env('FRONTEND_PLAN', 'Free') or 'Free'}",
            monthly_estimate_usd=frontend_cost,
            configured=azure_live is not None or frontend_estimate is not None,
            resource_id=", ".join(list(resources.get("frontend") or [])[:3]) or None,
            detail=(
                "Live month-to-date actual from Azure Cost Management."
                if azure_live
                else "Azure Static Web Apps plan estimate; the Free plan has no hosting charge."
            ),
        ),
    ]

    tracked = round(sum(item.monthly_estimate_usd or 0 for item in items if item.configured), 2)
    budget = _env_float("INFRA_MONTHLY_BUDGET_USD", 25.0) or 25.0
    missing = sum(not item.configured for item in items)
    provider_costs = {
        "Cloudflare R2": r2_estimate,
        "Railway": railway_cost,
        "Neon": neon_cost,
        "Microsoft Azure": azure_current_total,
    }
    provider_costs = {
        provider: round(float(cost), 2)
        for provider, cost in provider_costs.items()
        if cost is not None
    }
    history = _cost_history(
        db,
        current_provider_costs=provider_costs,
        current_estimated=True,
        current_paid_usd=_env_float("INFRA_CURRENT_MONTH_PAID_USD", 0.0) or 0.0,
    )
    current_point = history[-1]
    current_cost = current_point.total_usd or 0.0
    current_paid = current_point.paid_usd
    current_outstanding = current_point.outstanding_usd or 0.0
    available_points = [point for point in history if point.available]
    recorded_total = round(
        sum(point.total_usd or 0.0 for point in available_points), 2
    )
    recorded_paid = round(sum(point.paid_usd for point in available_points), 2)
    recorded_outstanding = round(
        sum(point.outstanding_usd or 0.0 for point in available_points), 2
    )
    return InfrastructureCostSummary(
        monthly_budget_usd=budget,
        tracked_monthly_estimate_usd=tracked,
        current_month_cost_usd=current_cost,
        current_month_paid_usd=current_paid,
        current_outstanding_usd=current_outstanding,
        recorded_total_usd=recorded_total,
        recorded_paid_usd=recorded_paid,
        recorded_outstanding_usd=recorded_outstanding,
        budget_utilization_percent=_percent(current_outstanding, budget) or 0.0,
        unconfigured_services=missing,
        basis=basis,
        source="Railway + Neon + retained Azure + Cloudflare R2",
        forecast_monthly_cost_usd=_env_float("INFRA_FORECAST_MONTHLY_COST_USD"),
        items=items,
        history=history,
        detail=(
            "The headline is the unpaid current-month amount. Provider actuals are used where "
            "supplied and plan estimates otherwise. Monthly snapshots are retained in the "
            "application database; INFRA_COST_HISTORY_JSON can backfill invoice totals and payments."
        ),
    )


def _alerts(
    storage_metrics: list[InfrastructureStorageMetric],
    compute_metrics: list[InfrastructureComputeMetric],
    connections: InfrastructureConnectionMetric,
    costs: InfrastructureCostSummary,
) -> list[InfrastructureAlert]:
    alerts: list[InfrastructureAlert] = []
    for metric in storage_metrics:
        if metric.status in {"warning", "critical"}:
            alerts.append(
                InfrastructureAlert(
                    severity=metric.status,
                    title=f"{metric.name} is {metric.utilization_percent:.0f}% full",
                    detail=f"Review the {metric.provider} allocation before capacity is exhausted.",
                )
            )
        elif metric.status == "unavailable":
            alerts.append(
                InfrastructureAlert(
                    severity="info",
                    title=f"{metric.name} telemetry unavailable",
                    detail=metric.detail,
                )
            )
    backend = next((item for item in compute_metrics if item.id == "backend"), None)
    if backend and backend.status in {"warning", "critical"}:
        alerts.append(
            InfrastructureAlert(
                severity=backend.status,
                title="Backend replica is under pressure",
                detail="CPU or memory utilization has crossed the capacity threshold.",
            )
        )
    if backend and backend.min_replicas == 0:
        alerts.append(
            InfrastructureAlert(
                severity="warning",
                title="Scale-to-zero can slow the first page load",
                detail=(
                    f"Low CPU/RAM does not rule out latency: an idle {backend.provider} instance "
                    "must cold-start before serving traffic. Keep one minimum replica when "
                    "consistent response time is worth the additional compute cost."
                ),
            )
        )
    if connections.status in {"warning", "critical"}:
        alerts.append(
            InfrastructureAlert(
                severity=connections.status,
                title="Database connection pool is saturated",
                detail=connections.detail,
            )
        )
    if costs.unconfigured_services:
        alerts.append(
            InfrastructureAlert(
                severity="info",
                title=f"{costs.unconfigured_services} cloud cost estimates need configuration",
                detail="Set the provider month-to-date cost environment variables shown in the service documentation.",
            )
        )
    if not alerts:
        alerts.append(
            InfrastructureAlert(
                severity="healthy",
                title="All measured resources are within target",
                detail="No measured resource has crossed the 75% warning threshold.",
            )
        )
    return alerts


def infrastructure_dashboard(db: Session, *, force_refresh: bool = False) -> InfrastructureDashboard:
    storage_metrics = [_r2_storage(force_refresh), _database_storage(db)]
    compute_metrics = _compute_metrics()
    connections = _database_connections(db)
    costs = _cost_summary(db, storage_metrics[0], force_refresh=force_refresh)
    return InfrastructureDashboard(
        collected_at=datetime.now(timezone.utc),
        refresh_after_seconds=30,
        storage=storage_metrics,
        compute=compute_metrics,
        database_connections=connections,
        quotas=[],
        costs=costs,
        alerts=_alerts(storage_metrics, compute_metrics, connections, costs),
    )
