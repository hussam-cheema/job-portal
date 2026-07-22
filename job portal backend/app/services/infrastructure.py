from __future__ import annotations

import math
import os
import resource
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import cfg, env, r2_enabled
from app.logging_config import get_logger
from app.schemas import (
    InfrastructureAlert,
    InfrastructureComputeMetric,
    InfrastructureConnectionMetric,
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
            provider="Azure PostgreSQL" if dialect == "postgresql" else "Local database",
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
            provider="Azure PostgreSQL",
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
            provider="Azure Container Apps",
            runtime_model="Dedicated per replica",
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
        ),
        InfrastructureComputeMetric(
            id="frontend",
            name="Frontend",
            provider="Azure Static Web Apps",
            runtime_model="Provider managed",
            status="managed",
            detail="Static Web Apps does not expose a fixed per-app CPU or RAM allocation.",
        ),
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


def _cost_summary(r2_metric: InfrastructureStorageMetric) -> InfrastructureCostSummary:
    # Cloudflare R2 Standard pricing, last verified 2026-07: first 10 GB-month free,
    # then USD 0.015/GB-month. This snapshot is directional, not an invoice.
    r2_gb = (r2_metric.used_bytes or 0) / GIB
    r2_billable_gb = math.ceil(max(0.0, r2_gb - 10.0))
    r2_estimate = round(r2_billable_gb * 0.015, 2)
    configured_costs = {
        "database": _env_float("DB_MONTHLY_COST_USD"),
        "backend": _env_float("BACKEND_MONTHLY_COST_USD"),
    }
    frontend_plan = (env("FRONTEND_PLAN", "Free") or "Free").lower()
    configured_costs["frontend"] = (
        _env_float("FRONTEND_MONTHLY_COST_USD")
        if env("FRONTEND_MONTHLY_COST_USD") is not None
        else (0.0 if frontend_plan == "free" else None)
    )
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
            id="database",
            name="Database",
            provider="Azure PostgreSQL",
            monthly_estimate_usd=configured_costs["database"],
            configured=configured_costs["database"] is not None,
            detail="Regional SKU and backup pricing; set DB_MONTHLY_COST_USD from Azure Cost Management.",
        ),
        InfrastructureCostItem(
            id="backend",
            name="Backend compute",
            provider="Azure Container Apps",
            monthly_estimate_usd=configured_costs["backend"],
            configured=configured_costs["backend"] is not None,
            detail="Consumption varies with replica activity; set BACKEND_MONTHLY_COST_USD from Azure Cost Management.",
        ),
        InfrastructureCostItem(
            id="frontend",
            name="Frontend hosting",
            provider=f"Azure Static Web Apps {env('FRONTEND_PLAN', 'Free') or 'Free'}",
            monthly_estimate_usd=configured_costs["frontend"],
            configured=configured_costs["frontend"] is not None,
            detail="Free plan is tracked as $0; configure FRONTEND_MONTHLY_COST_USD for a paid plan.",
        ),
    ]
    tracked = round(sum(item.monthly_estimate_usd or 0 for item in items if item.configured), 2)
    budget = _env_float("INFRA_MONTHLY_BUDGET_USD", 25.0) or 25.0
    missing = sum(not item.configured for item in items)
    return InfrastructureCostSummary(
        monthly_budget_usd=budget,
        tracked_monthly_estimate_usd=tracked,
        budget_utilization_percent=_percent(tracked, budget) or 0.0,
        unconfigured_services=missing,
        items=items,
        detail="Tracked estimates exclude unconfigured services and are not a substitute for provider invoices.",
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
                detail="Copy current monthly service estimates from Azure Cost Management into the documented environment variables.",
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
    costs = _cost_summary(storage_metrics[0])
    return InfrastructureDashboard(
        collected_at=datetime.now(timezone.utc),
        refresh_after_seconds=30,
        storage=storage_metrics,
        compute=compute_metrics,
        database_connections=connections,
        quotas=_quota_metrics(),
        costs=costs,
        alerts=_alerts(storage_metrics, compute_metrics, connections, costs),
    )
