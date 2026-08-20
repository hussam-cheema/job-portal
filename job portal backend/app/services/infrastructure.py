from __future__ import annotations

import json
import math
import os
import re
import resource
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import cfg, env, r2_enabled
from app.logging_config import get_logger
from app.models import (
    EmailSubscriber,
    InfrastructureCostSnapshot,
    Job,
    SubscriptionEmailDelivery,
)
from app.schemas import (
    InfrastructureAlert,
    InfrastructureComputeMetric,
    InfrastructureConnectionMetric,
    InfrastructureCostDriver,
    InfrastructureCostHistoryPoint,
    InfrastructureCostItem,
    InfrastructureCostSummary,
    InfrastructureDashboard,
    InfrastructureProviderBilling,
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
_provider_usage_cache_lock = threading.Lock()
_provider_usage_cache: dict[str, Any] = {}
_PROVIDER_USAGE_CACHE_SECONDS = 300

_R2_CLASS_A_ACTIONS = {
    "ListBuckets",
    "PutBucket",
    "ListObjects",
    "PutObject",
    "CopyObject",
    "CompleteMultipartUpload",
    "CreateMultipartUpload",
    "LifecycleStorageTierTransition",
    "ListMultipartUploads",
    "UploadPart",
    "UploadPartCopy",
    "ListParts",
    "PutBucketEncryption",
    "PutBucketCors",
    "PutBucketLifecycleConfiguration",
}
_R2_CLASS_B_ACTIONS = {
    "HeadBucket",
    "HeadObject",
    "GetObject",
    "UsageSummary",
    "GetBucketEncryption",
    "GetBucketLocation",
    "GetBucketCors",
    "GetBucketLifecycleConfiguration",
}


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


def _env_datetime(name: str) -> datetime | None:
    raw = (env(name) or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _calendar_billing_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _billing_window(prefix: str) -> tuple[datetime, datetime]:
    fallback_start, fallback_end = _calendar_billing_window()
    start = _env_datetime(f"{prefix}_BILLING_PERIOD_START") or fallback_start
    end = _env_datetime(f"{prefix}_BILLING_PERIOD_END") or fallback_end
    if end <= start:
        return fallback_start, fallback_end
    return start, end


def _project_month_end(
    value: float | None, start: datetime, end: datetime
) -> float | None:
    if value is None:
        return None
    now = datetime.now(timezone.utc)
    elapsed = max(
        3600.0, min((now - start).total_seconds(), (end - start).total_seconds())
    )
    total = max(elapsed, (end - start).total_seconds())
    return round(max(0.0, float(value)) * total / elapsed, 2)


def _remaining(used: float | None, included: float | None) -> float | None:
    if used is None or included is None:
        return None
    return round(max(0.0, included - used), 4)


def _driver_status(used: float | None, included: float | None) -> str:
    if used is None:
        return "unknown"
    return _status(_percent(used, included)) if included is not None else "healthy"


def _cached_provider_value(key: str, *, force_refresh: bool) -> Any | None:
    with _provider_usage_cache_lock:
        cached = _provider_usage_cache.get(key)
        if (
            cached
            and not force_refresh
            and time.monotonic() - cached["at"] < _PROVIDER_USAGE_CACHE_SECONDS
        ):
            return cached["value"]
    return None


def _store_provider_value(key: str, value: Any) -> Any:
    with _provider_usage_cache_lock:
        _provider_usage_cache[key] = {"at": time.monotonic(), "value": value}
    return value


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
        quota, period = (
            Path("/sys/fs/cgroup/cpu.max").read_text(encoding="utf-8").split()
        )
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
        resident_pages = int(
            Path("/proc/self/statm").read_text(encoding="utf-8").split()[1]
        )
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
    return round(
        min(100.0, (cpu_elapsed / elapsed / max(allocated_cores, 0.001)) * 100), 1
    )


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
        if (
            cached
            and not force_refresh
            and time.monotonic() - cached["at"] < _R2_CACHE_SECONDS
        ):
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
    database_provider = (
        env("DATABASE_PROVIDER", "Azure PostgreSQL") or "Azure PostgreSQL"
    )
    try:
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            used_bytes = int(
                db.execute(
                    text("SELECT pg_database_size(current_database())")
                ).scalar_one()
            )
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
    backend_provider = (
        env("BACKEND_PROVIDER", "Azure Container Apps") or "Azure Container Apps"
    )
    backend_runtime = (
        env("BACKEND_RUNTIME_MODEL", "Dedicated per replica") or "Dedicated per replica"
    )
    cpu_allocation = (
        _cgroup_cpu_limit() or _env_float("BACKEND_CPU_LIMIT_CORES", 0.5) or 0.5
    )
    memory_allocation = _cgroup_memory_limit()
    if memory_allocation is None:
        memory_allocation = int(
            (_env_float("BACKEND_MEMORY_LIMIT_MB", 1024.0) or 1024.0) * MIB
        )
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
    app_used_mb = _env_float("FRONTEND_APP_SIZE_MB")
    bandwidth_used_gb = _env_float("FRONTEND_BANDWIDTH_USED_GB")
    return [
        InfrastructureQuotaMetric(
            id="frontend_assets",
            name="Frontend app size",
            provider=f"Azure Static Web Apps {plan}",
            used=app_used_mb,
            total=app_limit_mb,
            unit="MB",
            utilization_percent=_percent(app_used_mb, app_limit_mb),
            status=_driver_status(app_used_mb, app_limit_mb),
            detail="Per-app deployment limit; configure the current artifact size when Azure does not expose it to the backend.",
        ),
        InfrastructureQuotaMetric(
            id="frontend_bandwidth",
            name="Frontend bandwidth",
            provider=f"Azure Static Web Apps {plan}",
            used=bandwidth_used_gb,
            total=bandwidth_limit_gb,
            unit="GB/month",
            utilization_percent=_percent(bandwidth_used_gb, bandwidth_limit_gb),
            status=_driver_status(bandwidth_used_gb, bandwidth_limit_gb),
            detail="Free serves up to 100 GB per subscription each month; live usage requires Azure telemetry or configuration.",
        ),
    ]


def _neon_usage(
    database_metric: InfrastructureStorageMetric,
    *,
    force_refresh: bool,
) -> dict[str, Any]:
    start, end = _billing_window("NEON")
    fallback = {
        "compute_cu_hours": _env_float("NEON_COMPUTE_CU_HOURS"),
        "storage_gb": (
            (database_metric.used_bytes or 0) / GIB
            if database_metric.used_bytes is not None
            else None
        ),
        "history_gb": _env_float("NEON_HISTORY_STORAGE_GB"),
        "network_gb": _env_float("NEON_NETWORK_TRANSFER_GB"),
        "branch_count": _env_float("NEON_BRANCH_COUNT"),
        "period_start": start,
        "period_end": end,
        "source": "PostgreSQL size + configuration",
        "configured": False,
    }
    api_key = env("NEON_API_KEY")
    project_id = env("NEON_PROJECT_ID")
    if not api_key or not project_id:
        return fallback
    cache_key = f"neon:{project_id}"
    cached = _cached_provider_value(cache_key, force_refresh=force_refresh)
    if cached is not None:
        return cached
    try:
        response = httpx.get(
            f"https://console.neon.tech/api/v2/projects/{project_id}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=12.0,
        )
        response.raise_for_status()
        project = response.json().get("project") or {}
        api_start = project.get("consumption_period_start")
        api_end = project.get("consumption_period_end")
        if api_start:
            try:
                start = datetime.fromisoformat(str(api_start).replace("Z", "+00:00"))
            except ValueError:
                pass
        if api_end:
            try:
                end = datetime.fromisoformat(str(api_end).replace("Z", "+00:00"))
            except ValueError:
                pass
        elapsed_hours = max(
            1.0, (datetime.now(timezone.utc) - start).total_seconds() / 3600
        )
        storage_byte_hours = float(project.get("data_storage_bytes_hour") or 0)
        storage_gb = (
            storage_byte_hours / elapsed_hours / GIB
            if storage_byte_hours > 0
            else fallback["storage_gb"]
        )
        branch_count = fallback["branch_count"]
        try:
            branch_response = httpx.get(
                f"https://console.neon.tech/api/v2/projects/{project_id}/branches/count",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
                timeout=12.0,
            )
            branch_response.raise_for_status()
            raw_branch_count = branch_response.json().get("count")
            if raw_branch_count is not None:
                branch_count = float(raw_branch_count)
        except Exception:
            logger.warning("Neon branch count collection failed project=%s", project_id)
        value = {
            "compute_cu_hours": round(
                float(project.get("cpu_used_sec") or 0) / 3600, 2
            ),
            "storage_gb": round(float(storage_gb or 0), 4),
            # Free-plan history is limited by retained time or data changes.
            # written_data_bytes is the closest all-plan API signal for that
            # pressure; paid plans can override with the exact history metric.
            "history_gb": (
                _env_float("NEON_HISTORY_STORAGE_GB")
                if env("NEON_HISTORY_STORAGE_GB") is not None
                else round(float(project.get("written_data_bytes") or 0) / GIB, 4)
            ),
            "network_gb": round(
                float(project.get("data_transfer_bytes") or 0) / GIB, 4
            ),
            "branch_count": branch_count,
            "period_start": start,
            "period_end": end,
            "source": "Neon project details API (cached up to 5 min)",
            "configured": True,
        }
        return _store_provider_value(cache_key, value)
    except Exception:
        logger.exception("Neon usage collection failed project=%s", project_id)
        fallback["source"] = (
            "Neon API unavailable; PostgreSQL size + configuration fallback"
        )
        return fallback


def _quota_header_used(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group(0)) if match else None


def _resend_usage(db: Session, *, force_refresh: bool) -> dict[str, Any]:
    start, end = _billing_window("RESEND")
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start_naive = start.replace(tzinfo=None)
    day_start_naive = day_start.replace(tzinfo=None)
    delivered_month = int(
        db.execute(
            select(func.count(SubscriptionEmailDelivery.id)).where(
                SubscriptionEmailDelivery.delivered_at >= month_start_naive
            )
        ).scalar_one()
    )
    delivered_today = int(
        db.execute(
            select(func.count(SubscriptionEmailDelivery.id)).where(
                SubscriptionEmailDelivery.delivered_at >= day_start_naive
            )
        ).scalar_one()
    )
    active_subscribers = int(
        db.execute(
            select(func.count(EmailSubscriber.user_uuid)).where(
                EmailSubscriber.is_active.is_(True)
            )
        ).scalar_one()
    )
    jobs_this_month = int(
        db.execute(
            select(func.count(Job.id)).where(Job.created_at >= month_start_naive)
        ).scalar_one()
    )
    value = {
        "monthly_used": float(delivered_month),
        "daily_used": float(delivered_today),
        "active_subscribers": float(active_subscribers),
        "jobs_this_month": float(jobs_this_month),
        "period_start": start,
        "period_end": end,
        "source": "Application delivery ledger",
        "configured": False,
    }
    api_key = env("RESEND_API_KEY")
    if not api_key:
        return value
    cache_key = "resend:quota"
    cached = _cached_provider_value(cache_key, force_refresh=force_refresh)
    if cached is not None:
        # Subscriber/job demand is local and should not be frozen with the API cache.
        return {
            **cached,
            "active_subscribers": float(active_subscribers),
            "jobs_this_month": float(jobs_this_month),
        }
    try:
        api_url = (env("RESEND_API_URL") or "https://api.resend.com/emails").rstrip("/")
        response = httpx.get(
            api_url,
            params={"limit": 1},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "pakistan-jobs-market-infrastructure/1.0",
            },
            timeout=10.0,
        )
        response.raise_for_status()
        monthly_header = _quota_header_used(
            response.headers.get("x-resend-monthly-quota")
        )
        daily_header = _quota_header_used(response.headers.get("x-resend-daily-quota"))
        value.update(
            {
                "monthly_used": monthly_header
                if monthly_header is not None
                else float(delivered_month),
                "daily_used": daily_header
                if daily_header is not None
                else float(delivered_today),
                "source": (
                    "Resend quota headers (cached up to 5 min)"
                    if monthly_header is not None
                    else "Resend API reachable; application delivery ledger"
                ),
                "configured": True,
            }
        )
        return _store_provider_value(cache_key, value)
    except Exception:
        logger.exception("Resend quota collection failed")
        value["source"] = "Resend API unavailable; application delivery ledger fallback"
        return value


def _r2_operation_usage(*, force_refresh: bool) -> dict[str, Any]:
    start, end = _billing_window("R2")
    fallback = {
        "class_a": _env_float("R2_CLASS_A_OPERATIONS"),
        "class_b": _env_float("R2_CLASS_B_OPERATIONS"),
        "period_start": start,
        "period_end": end,
        "source": "configuration",
        "configured": False,
    }
    token = env("CLOUDFLARE_API_TOKEN")
    account_id = env("R2_ACCOUNT_ID")
    bucket = storage._bucket()
    if not token or not account_id or not bucket:
        return fallback
    cache_key = f"r2-operations:{account_id}:{bucket}"
    cached = _cached_provider_value(cache_key, force_refresh=force_refresh)
    if cached is not None:
        return cached
    query = """
    query R2Operations($accountTag: string!, $startDate: Time, $endDate: Time, $bucketName: string) {
      viewer {
        accounts(filter: {accountTag: $accountTag}) {
          r2OperationsAdaptiveGroups(
            limit: 10000
            filter: {datetime_geq: $startDate, datetime_leq: $endDate, bucketName: $bucketName}
          ) {
            sum { requests }
            dimensions { actionType }
          }
        }
      }
    }
    """
    try:
        response = httpx.post(
            "https://api.cloudflare.com/client/v4/graphql",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": query,
                "variables": {
                    "accountTag": account_id,
                    "startDate": start.isoformat().replace("+00:00", "Z"),
                    "endDate": min(datetime.now(timezone.utc), end)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "bucketName": bucket,
                },
            },
            timeout=12.0,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(str(payload["errors"])[:300])
        accounts = ((payload.get("data") or {}).get("viewer") or {}).get(
            "accounts"
        ) or []
        groups = (
            (accounts[0].get("r2OperationsAdaptiveGroups") or []) if accounts else []
        )
        class_a = 0.0
        class_b = 0.0
        for group in groups:
            action = str((group.get("dimensions") or {}).get("actionType") or "")
            requests = float((group.get("sum") or {}).get("requests") or 0)
            if action in _R2_CLASS_A_ACTIONS:
                class_a += requests
            elif action in _R2_CLASS_B_ACTIONS:
                class_b += requests
        value = {
            "class_a": class_a,
            "class_b": class_b,
            "period_start": start,
            "period_end": end,
            "source": "Cloudflare GraphQL Analytics API (cached up to 5 min)",
            "configured": True,
        }
        return _store_provider_value(cache_key, value)
    except Exception:
        logger.exception("Cloudflare R2 operation collection failed bucket=%s", bucket)
        fallback["source"] = "Cloudflare Analytics unavailable; configuration fallback"
        return fallback


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
                "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
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
            properties = _query_azure_cost_scope(scope, token).get("properties") or {}
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
        existing_rows = (
            db.execute(
                select(InfrastructureCostSnapshot).where(
                    InfrastructureCostSnapshot.month == current_month,
                    InfrastructureCostSnapshot.provider.in_(current_provider_costs),
                )
            )
            .scalars()
            .all()
        )
        existing_by_provider = {row.provider: row for row in existing_rows}
        for provider, cost in current_provider_costs.items():
            row = existing_by_provider.get(provider)
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
        estimated_by_month[row.month] = estimated_by_month.get(
            row.month, False
        ) or bool(row.estimated)

    manual = _manual_cost_history()
    for month, entry in manual.items():
        if month in months:
            by_month[month] = entry["provider_costs"]
            estimated_by_month[month] = False

    # Railway and Neon did not exist before cutover. That fact does not imply
    # the retired Azure stack cost $0, so an unbackfilled month is deliberately
    # marked unavailable instead of presenting a misleading zero total.
    stack_started = (
        env("INFRA_CURRENT_STACK_STARTED_MONTH", current_month) or current_month
    )
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
            source = (
                "manual invoice backfill"
                if month in manual
                else "stored monthly snapshot"
            )
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


def _r2_standard_cost(storage_gb: float, class_a: float, class_b: float) -> float:
    storage_blocks = math.ceil(max(0.0, storage_gb - 10.0))
    class_a_blocks = math.ceil(max(0.0, class_a - 1_000_000.0) / 1_000_000.0)
    class_b_blocks = math.ceil(max(0.0, class_b - 10_000_000.0) / 1_000_000.0)
    return round(
        storage_blocks * 0.015 + class_a_blocks * 4.50 + class_b_blocks * 0.36, 2
    )


def _provider_usage_dashboard(
    db: Session,
    r2_metric: InfrastructureStorageMetric,
    database_metric: InfrastructureStorageMetric,
    *,
    force_refresh: bool,
) -> tuple[list[InfrastructureCostDriver], list[InfrastructureProviderBilling]]:
    drivers: list[InfrastructureCostDriver] = []
    providers: list[InfrastructureProviderBilling] = []

    # Railway Free is genuinely $0/month with $1 of monthly resource credit.
    # The old RAILWAY_PLAN/RAILWAY_MONTHLY_COST_USD variables represented the
    # anticipated Hobby upgrade and must not create a debt while this workspace
    # is still on Free. RAILWAY_SUBSCRIPTION_PLAN is the authoritative setting.
    railway_plan = env("RAILWAY_SUBSCRIPTION_PLAN", "Free") or "Free"
    railway_plan_key = railway_plan.casefold()
    railway_start, railway_end = _billing_window("RAILWAY")
    railway_subscription = (
        _env_float(
            "RAILWAY_SUBSCRIPTION_FEE_USD",
            {"free": 0.0, "hobby": 5.0, "pro": 20.0}.get(railway_plan_key, 0.0),
        )
        or 0.0
    )
    railway_credit = (
        _env_float(
            "RAILWAY_INCLUDED_USAGE_USD",
            {"free": 1.0, "hobby": 5.0, "pro": 20.0}.get(railway_plan_key, 0.0),
        )
        or 0.0
    )
    railway_cpu = _env_float("RAILWAY_CPU_VCPU_HOURS")
    railway_memory = _env_float("RAILWAY_MEMORY_GB_HOURS")
    railway_egress = _env_float("RAILWAY_NETWORK_EGRESS_GB")
    railway_volume = _env_float("RAILWAY_VOLUME_GB_MONTHS")
    calculated_railway_usage = (
        (railway_cpu or 0) * (20 / 730)
        + (railway_memory or 0) * (10 / 730)
        + (railway_egress or 0) * 0.05
        + (railway_volume or 0) * 0.15
        if any(
            value is not None
            for value in (railway_cpu, railway_memory, railway_egress, railway_volume)
        )
        else None
    )
    railway_usage = _env_float("RAILWAY_CURRENT_USAGE_USD")
    if railway_usage is None:
        railway_usage = _env_float("RAILWAY_MONTH_TO_DATE_COST_USD")
    if railway_usage is None:
        railway_usage = calculated_railway_usage
    railway_projected = _env_float("RAILWAY_PROJECTED_USAGE_USD")
    if railway_projected is None:
        railway_projected = _project_month_end(
            railway_usage, railway_start, railway_end
        )
    railway_due = (
        0.0
        if railway_plan_key == "free"
        else round(max(railway_subscription, railway_usage or 0.0), 2)
    )
    railway_projected_due = (
        0.0
        if railway_plan_key == "free"
        else round(max(railway_subscription, railway_projected or 0.0), 2)
    )
    railway_source = (
        "Railway Usage configuration"
        if railway_usage is not None
        else "Railway Free subscription limits; add usage values for live spend"
    )
    providers.append(
        InfrastructureProviderBilling(
            id="railway",
            provider="Railway",
            plan=railway_plan,
            subscription_fee_usd=railway_subscription,
            included_credit_usd=railway_credit,
            current_usage_usd=round(railway_usage, 2)
            if railway_usage is not None
            else None,
            current_amount_due_usd=railway_due,
            projected_usage_usd=round(railway_projected, 2)
            if railway_projected is not None
            else None,
            projected_amount_due_usd=railway_projected_due,
            billing_period_start=railway_start,
            billing_period_end=railway_end,
            next_charge_at=railway_end if railway_plan_key != "free" else None,
            configured=railway_usage is not None,
            status=_driver_status(railway_usage, railway_credit),
            source=railway_source,
            detail=(
                "No $5 is currently owed. Free workloads can use $1 of monthly resources; "
                "at that limit they must wait for the next reset or upgrade to Hobby ($5/month, "
                "including the first $5 of usage)."
                if railway_plan_key == "free"
                else f"The ${railway_subscription:.0f} subscription is the minimum monthly commitment and offsets the first ${railway_credit:.0f} of usage."
            ),
        )
    )
    drivers.append(
        InfrastructureCostDriver(
            id="railway_usage_credit",
            provider="Railway",
            service="Backend API + newsletter retry",
            plan=railway_plan,
            metric="Resource usage credit",
            used=round(railway_usage, 4) if railway_usage is not None else None,
            included=railway_credit,
            remaining=_remaining(railway_usage, railway_credit),
            unit="USD",
            utilization_percent=_percent(railway_usage, railway_credit),
            projected_month_end=railway_projected,
            current_cost_usd=railway_due,
            projected_cost_usd=railway_projected_due,
            next_paid_increment_usd=5.0 if railway_plan_key == "free" else None,
            status=_driver_status(railway_usage, railway_credit),
            source=railway_source,
            detail="CPU, RAM, volume storage, and public network egress all consume this shared credit.",
        )
    )
    railway_components = [
        (
            "railway_cpu",
            "CPU time",
            railway_cpu,
            "vCPU-hours",
            20 / 730,
            "$20/vCPU-month",
        ),
        (
            "railway_memory",
            "Memory time",
            railway_memory,
            "GB-hours",
            10 / 730,
            "$10/GB-month",
        ),
        ("railway_network", "Network egress", railway_egress, "GB", 0.05, "$0.05/GB"),
        (
            "railway_volume",
            "Volume storage",
            railway_volume,
            "GB-month",
            0.15,
            "$0.15/GB-month",
        ),
    ]
    for driver_id, metric, used, unit, rate, rate_label in railway_components:
        projected = _project_month_end(used, railway_start, railway_end)
        drivers.append(
            InfrastructureCostDriver(
                id=driver_id,
                provider="Railway",
                service="Backend API + newsletter retry",
                plan=railway_plan,
                metric=metric,
                used=used,
                unit=unit,
                projected_month_end=projected,
                current_cost_usd=round(used * rate, 2) if used is not None else None,
                projected_cost_usd=round(projected * rate, 2)
                if projected is not None
                else None,
                status="healthy" if used is not None else "unknown",
                source="Railway Usage configuration",
                detail=f"Gross usage rate {rate_label}; the plan's shared credit is applied after these components are summed.",
            )
        )

    neon_usage = _neon_usage(database_metric, force_refresh=force_refresh)
    neon_plan = env("NEON_PLAN", "Free") or "Free"
    neon_plan_key = neon_plan.casefold()
    neon_start = neon_usage["period_start"]
    neon_end = neon_usage["period_end"]
    neon_allowances = (
        {"compute": 100.0, "storage": 0.5, "history": 1.0, "network": 5.0}
        if neon_plan_key == "free"
        else {"compute": None, "storage": None, "history": None, "network": 100.0}
    )
    neon_rates = {"compute": 0.106, "storage": 0.35, "history": 0.20, "network": 0.10}
    neon_values = {
        "compute": neon_usage["compute_cu_hours"],
        "storage": neon_usage["storage_gb"],
        "history": neon_usage["history_gb"],
        "network": neon_usage["network_gb"],
    }
    neon_projected = {
        key: (
            value
            if key in {"storage", "history"}
            else _project_month_end(value, neon_start, neon_end)
        )
        for key, value in neon_values.items()
    }
    launch_equivalent = round(
        (neon_projected["compute"] or 0) * neon_rates["compute"]
        + (neon_projected["storage"] or 0) * neon_rates["storage"]
        + (neon_projected["history"] or 0) * neon_rates["history"]
        + max(0.0, (neon_projected["network"] or 0) - 100.0) * neon_rates["network"],
        2,
    )
    neon_subscription = _env_float("NEON_SUBSCRIPTION_FEE_USD", 0.0) or 0.0
    neon_due = (
        0.0
        if neon_plan_key == "free"
        else round(
            (neon_values["compute"] or 0) * neon_rates["compute"]
            + (neon_values["storage"] or 0) * neon_rates["storage"]
            + (neon_values["history"] or 0) * neon_rates["history"]
            + max(0.0, (neon_values["network"] or 0) - 100.0) * neon_rates["network"],
            2,
        )
    )
    providers.append(
        InfrastructureProviderBilling(
            id="neon",
            provider="Neon",
            plan=neon_plan,
            subscription_fee_usd=neon_subscription,
            current_usage_usd=neon_due,
            current_amount_due_usd=neon_due,
            projected_usage_usd=launch_equivalent
            if neon_plan_key == "free"
            else neon_due,
            projected_amount_due_usd=0.0
            if neon_plan_key == "free"
            else launch_equivalent,
            billing_period_start=neon_start,
            billing_period_end=neon_end,
            next_charge_at=neon_end if neon_plan_key != "free" else None,
            configured=bool(neon_usage["configured"]),
            status=max(
                (
                    _driver_status(neon_values[key], neon_allowances[key])
                    for key in neon_values
                ),
                key=lambda value: {
                    "unknown": 0,
                    "healthy": 1,
                    "warning": 2,
                    "critical": 3,
                }.get(value, 0),
            ),
            source=neon_usage["source"],
            detail=(
                f"Free creates no invoice. If its limits require an upgrade, the current month-end workload is approximately ${launch_equivalent:.2f} on Launch before branch-hour charges."
                if neon_plan_key == "free"
                else "Usage-based estimate uses current Launch rates for compute, storage, history, and network transfer."
            ),
        )
    )
    neon_driver_specs = [
        ("neon_compute", "Compute", "compute", "CU-hours", "$0.106/CU-hour on Launch"),
        (
            "neon_storage",
            "Database storage",
            "storage",
            "GB",
            "$0.35/GB-month on Launch",
        ),
        (
            "neon_history",
            "History data changes",
            "history",
            "GB",
            "$0.20/GB-month on Launch",
        ),
        (
            "neon_network",
            "Public network transfer",
            "network",
            "GB",
            "$0.10/GB after 100 GB on Launch",
        ),
    ]
    for driver_id, metric, key, unit, rate_label in neon_driver_specs:
        used = neon_values[key]
        included = neon_allowances[key]
        projected = neon_projected[key]
        paid_equivalent = (
            max(0.0, (projected or 0) - 100.0) * neon_rates[key]
            if key == "network"
            else (projected or 0) * neon_rates[key]
        )
        drivers.append(
            InfrastructureCostDriver(
                id=driver_id,
                provider="Neon",
                service="PostgreSQL database",
                plan=neon_plan,
                metric=metric,
                used=used,
                included=included,
                remaining=_remaining(used, included),
                unit=unit,
                utilization_percent=_percent(used, included),
                projected_month_end=projected,
                current_cost_usd=0.0
                if neon_plan_key == "free"
                else round(paid_equivalent, 2),
                projected_cost_usd=round(paid_equivalent, 2),
                next_paid_increment_usd=round(paid_equivalent, 2)
                if neon_plan_key == "free"
                else None,
                status=_driver_status(used, included),
                source=neon_usage["source"],
                detail=(
                    f"Free allowance; exceeding it suspends the relevant compute until reset or upgrade. Paid reference: {rate_label}."
                    if neon_plan_key == "free"
                    else f"Usage-based rate: {rate_label}."
                ),
            )
        )
    neon_branches = neon_usage["branch_count"]
    drivers.append(
        InfrastructureCostDriver(
            id="neon_branches",
            provider="Neon",
            service="PostgreSQL database",
            plan=neon_plan,
            metric="Active branches",
            used=neon_branches,
            included=10.0,
            remaining=_remaining(neon_branches, 10.0),
            unit="branches",
            utilization_percent=_percent(neon_branches, 10.0),
            next_paid_increment_usd=0.002,
            status=_driver_status(neon_branches, 10.0),
            source=neon_usage["source"],
            detail=(
                "Free permits 10 branches per project. Launch also includes 10, then charges approximately $0.002 per additional branch-hour."
            ),
        )
    )

    resend_usage = _resend_usage(db, force_refresh=force_refresh)
    resend_plan = env("RESEND_PLAN", "Free") or "Free"
    resend_plan_key = resend_plan.casefold()
    resend_monthly_limit = (
        _env_float(
            "RESEND_MONTHLY_EMAIL_LIMIT",
            3000.0 if resend_plan_key == "free" else 50_000.0,
        )
        or 3000.0
    )
    resend_daily_limit = (
        _env_float("RESEND_DAILY_EMAIL_LIMIT", 100.0)
        if resend_plan_key == "free"
        else None
    )
    resend_subscription = (
        _env_float(
            "RESEND_SUBSCRIPTION_FEE_USD",
            0.0 if resend_plan_key == "free" else 20.0,
        )
        or 0.0
    )
    resend_monthly_used = resend_usage["monthly_used"]
    resend_projected = _project_month_end(
        resend_monthly_used,
        resend_usage["period_start"],
        resend_usage["period_end"],
    )
    resend_overage = (
        max(0.0, (resend_monthly_used or 0) - resend_monthly_limit) / 1000 * 0.90
        if resend_plan_key != "free"
        else 0.0
    )
    resend_projected_overage = (
        max(0.0, (resend_projected or 0) - resend_monthly_limit) / 1000 * 0.90
        if resend_plan_key != "free"
        else 0.0
    )
    providers.append(
        InfrastructureProviderBilling(
            id="resend",
            provider="Resend",
            plan=resend_plan,
            subscription_fee_usd=resend_subscription,
            current_usage_usd=round(resend_subscription + resend_overage, 2),
            current_amount_due_usd=round(resend_subscription + resend_overage, 2),
            projected_usage_usd=round(
                resend_subscription + resend_projected_overage, 2
            ),
            projected_amount_due_usd=round(
                resend_subscription + resend_projected_overage, 2
            ),
            billing_period_start=resend_usage["period_start"],
            billing_period_end=resend_usage["period_end"],
            next_charge_at=resend_usage["period_end"]
            if resend_plan_key != "free"
            else None,
            configured=bool(resend_usage["configured"]),
            status=_driver_status(resend_monthly_used, resend_monthly_limit),
            source=resend_usage["source"],
            detail=(
                "Free includes 3,000 emails per month and 100 per day. At either limit, sending pauses; Pro starts at $20/month for 50,000 emails."
                if resend_plan_key == "free"
                else "Pro includes 50,000 monthly emails; additional emails are estimated at $0.90 per 1,000."
            ),
        )
    )
    drivers.extend(
        [
            InfrastructureCostDriver(
                id="resend_monthly_emails",
                provider="Resend",
                service="Transactional email",
                plan=resend_plan,
                metric="Monthly emails",
                used=resend_monthly_used,
                included=resend_monthly_limit,
                remaining=_remaining(resend_monthly_used, resend_monthly_limit),
                unit="emails/month",
                utilization_percent=_percent(resend_monthly_used, resend_monthly_limit),
                projected_month_end=resend_projected,
                current_cost_usd=round(resend_subscription + resend_overage, 2),
                projected_cost_usd=round(
                    resend_subscription + resend_projected_overage, 2
                ),
                next_paid_increment_usd=20.0 if resend_plan_key == "free" else 0.90,
                status=_driver_status(resend_monthly_used, resend_monthly_limit),
                source=resend_usage["source"],
                detail="Every To, CC, or BCC recipient counts separately; inbound mail also counts in Resend's provider total.",
            ),
            InfrastructureCostDriver(
                id="resend_daily_emails",
                provider="Resend",
                service="Transactional email",
                plan=resend_plan,
                metric="Daily emails",
                used=resend_usage["daily_used"],
                included=resend_daily_limit,
                remaining=_remaining(resend_usage["daily_used"], resend_daily_limit),
                unit="emails/day",
                utilization_percent=_percent(
                    resend_usage["daily_used"], resend_daily_limit
                ),
                next_paid_increment_usd=20.0 if resend_plan_key == "free" else None,
                status=_driver_status(resend_usage["daily_used"], resend_daily_limit),
                source=resend_usage["source"],
                detail=f"Demand signal: {int(resend_usage['active_subscribers'])} active subscribers and {int(resend_usage['jobs_this_month'])} jobs created this billing month.",
            ),
        ]
    )

    r2_usage = _r2_operation_usage(force_refresh=force_refresh)
    r2_start, r2_end = r2_usage["period_start"], r2_usage["period_end"]
    r2_storage_gb = (r2_metric.used_bytes or 0) / GIB
    r2_a = r2_usage["class_a"]
    r2_b = r2_usage["class_b"]
    r2_current = _r2_standard_cost(r2_storage_gb, r2_a or 0, r2_b or 0)
    r2_projected_a = _project_month_end(r2_a, r2_start, r2_end)
    r2_projected_b = _project_month_end(r2_b, r2_start, r2_end)
    r2_projected = _r2_standard_cost(
        r2_storage_gb,
        r2_projected_a or r2_a or 0,
        r2_projected_b or r2_b or 0,
    )
    providers.append(
        InfrastructureProviderBilling(
            id="r2",
            provider="Cloudflare R2",
            plan="Standard",
            current_usage_usd=r2_current,
            current_amount_due_usd=r2_current,
            projected_usage_usd=r2_projected,
            projected_amount_due_usd=r2_projected,
            billing_period_start=r2_start,
            billing_period_end=r2_end,
            next_charge_at=r2_end if r2_projected > 0 else None,
            configured=r2_metric.status != "unavailable",
            status=max(
                (
                    _driver_status(r2_storage_gb, 10),
                    _driver_status(r2_a, 1_000_000),
                    _driver_status(r2_b, 10_000_000),
                ),
                key=lambda value: {
                    "unknown": 0,
                    "healthy": 1,
                    "warning": 2,
                    "critical": 3,
                }.get(value, 0),
            ),
            source=f"{r2_metric.source}; {r2_usage['source']}",
            detail="R2 egress is free. Cost is driven by average Standard storage plus Class A writes/lists and Class B reads; usage is rounded to billing blocks.",
        )
    )
    r2_specs = [
        (
            "r2_storage",
            "Stored data snapshot",
            r2_storage_gb,
            10.0,
            "GB-month",
            0.015,
            "Next GB-month above the free tier",
        ),
        (
            "r2_class_a",
            "Class A operations",
            r2_a,
            1_000_000.0,
            "requests/month",
            4.50,
            "Next million Class A requests",
        ),
        (
            "r2_class_b",
            "Class B operations",
            r2_b,
            10_000_000.0,
            "requests/month",
            0.36,
            "Next million Class B requests",
        ),
    ]
    for driver_id, metric, used, included, unit, next_cost, detail in r2_specs:
        projected = (
            used
            if driver_id == "r2_storage"
            else _project_month_end(used, r2_start, r2_end)
        )
        drivers.append(
            InfrastructureCostDriver(
                id=driver_id,
                provider="Cloudflare R2",
                service="Object storage",
                plan="Standard",
                metric=metric,
                used=round(used, 4) if used is not None else None,
                included=included,
                remaining=_remaining(used, included),
                unit=unit,
                utilization_percent=_percent(used, included),
                projected_month_end=projected,
                current_cost_usd=r2_current,
                projected_cost_usd=r2_projected,
                next_paid_increment_usd=next_cost,
                status=_driver_status(used, included),
                source=r2_metric.source
                if driver_id == "r2_storage"
                else r2_usage["source"],
                detail=(
                    f"{detail}; billing averages the daily peak storage over the month, "
                    "and Internet egress remains $0."
                    if driver_id == "r2_storage"
                    else f"{detail}; Internet egress remains $0."
                ),
            )
        )

    frontend_plan = env("FRONTEND_PLAN", "Free") or "Free"
    azure_start, azure_end = _billing_window("AZURE")
    frontend_bandwidth = _env_float("FRONTEND_BANDWIDTH_USED_GB")
    frontend_app_size = _env_float("FRONTEND_APP_SIZE_MB")
    for driver_id, metric, used, included, unit, detail in [
        (
            "azure_bandwidth",
            "Frontend bandwidth",
            frontend_bandwidth,
            _env_float("FRONTEND_BANDWIDTH_LIMIT_GB", 100.0),
            "GB/month",
            "Free cannot serve beyond 100 GB; Standard supports $0.20/GB overage.",
        ),
        (
            "azure_app_size",
            "Deployed app size",
            frontend_app_size,
            _env_float("FRONTEND_APP_LIMIT_MB", 250.0),
            "MB",
            "Free permits 250 MB per deployed app and 500 MB across environments.",
        ),
    ]:
        drivers.append(
            InfrastructureCostDriver(
                id=driver_id,
                provider="Microsoft Azure",
                service="Static Web Apps frontend",
                plan=frontend_plan,
                metric=metric,
                used=used,
                included=included,
                remaining=_remaining(used, included),
                unit=unit,
                utilization_percent=_percent(used, included),
                projected_month_end=(
                    _project_month_end(used, azure_start, azure_end)
                    if driver_id == "azure_bandwidth"
                    else used
                ),
                next_paid_increment_usd=(
                    0.20 if driver_id == "azure_bandwidth" else None
                ),
                status=_driver_status(used, included),
                source="Azure quota configuration",
                detail=detail,
            )
        )
    return drivers, providers


def _cost_summary(
    db: Session,
    provider_billing: list[InfrastructureProviderBilling],
    *,
    force_refresh: bool,
) -> tuple[InfrastructureCostSummary, InfrastructureProviderBilling]:
    billing_by_id = {item.id: item for item in provider_billing}
    r2_estimate = billing_by_id["r2"].current_amount_due_usd
    railway_plan = billing_by_id["railway"].plan
    railway_cost = billing_by_id["railway"].current_amount_due_usd
    neon_plan = billing_by_id["neon"].plan
    neon_cost = billing_by_id["neon"].current_amount_due_usd
    resend_cost = billing_by_id["resend"].current_amount_due_usd

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
    has_actual = (
        any(item.configured for item in provider_billing) or azure_live is not None
    )
    basis = "provider_actuals_and_estimates" if has_actual else "monthly_estimate"

    items = [
        InfrastructureCostItem(
            id="r2",
            name="Object storage",
            provider="Cloudflare R2 Standard",
            monthly_estimate_usd=r2_estimate,
            configured=billing_by_id["r2"].configured,
            detail="Live storage plus Class A/B operation estimate. Internet egress is free.",
        ),
        InfrastructureCostItem(
            id="railway",
            name="Backend API + newsletter retry",
            provider=f"Railway {railway_plan}",
            monthly_estimate_usd=railway_cost,
            configured=railway_cost is not None,
            detail=billing_by_id["railway"].detail,
        ),
        InfrastructureCostItem(
            id="neon",
            name="PostgreSQL database",
            provider=f"Neon {neon_plan}",
            monthly_estimate_usd=neon_cost,
            configured=neon_cost is not None,
            detail=billing_by_id["neon"].detail,
        ),
        InfrastructureCostItem(
            id="resend",
            name="Transactional email",
            provider=f"Resend {billing_by_id['resend'].plan}",
            monthly_estimate_usd=resend_cost,
            configured=billing_by_id["resend"].configured,
            detail=billing_by_id["resend"].detail,
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

    tracked = round(
        sum(item.monthly_estimate_usd or 0 for item in items if item.configured), 2
    )
    budget = _env_float("INFRA_MONTHLY_BUDGET_USD", 25.0) or 25.0
    missing = sum(not item.configured for item in items)
    provider_costs = {
        "Cloudflare R2": r2_estimate,
        "Railway": railway_cost,
        "Neon": neon_cost,
        "Resend": resend_cost,
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
    recorded_total = round(sum(point.total_usd or 0.0 for point in available_points), 2)
    recorded_paid = round(sum(point.paid_usd for point in available_points), 2)
    recorded_outstanding = round(
        sum(point.outstanding_usd or 0.0 for point in available_points), 2
    )
    azure_billing = InfrastructureProviderBilling(
        id="azure",
        provider="Microsoft Azure",
        plan=env("FRONTEND_PLAN", "Free") or "Free",
        current_usage_usd=azure_current_total,
        current_amount_due_usd=azure_current_total or 0.0,
        projected_usage_usd=(
            _env_float("AZURE_PROJECTED_COST_USD")
            if env("AZURE_PROJECTED_COST_USD") is not None
            else azure_current_total
        ),
        projected_amount_due_usd=(
            _env_float("AZURE_PROJECTED_COST_USD")
            if env("AZURE_PROJECTED_COST_USD") is not None
            else azure_current_total
        ),
        billing_period_start=_billing_window("AZURE")[0],
        billing_period_end=_billing_window("AZURE")[1],
        next_charge_at=_billing_window("AZURE")[1]
        if (azure_current_total or 0) > 0
        else None,
        configured=azure_live is not None or frontend_estimate is not None,
        status="healthy",
        source="Azure Cost Management" if azure_live else "Azure plan configuration",
        detail=(
            "Live month-to-date Azure costs, including charges accrued by resources retired during this billing month."
            if azure_live
            else "Static Web Apps Free has no subscription fee; exceeding its quota stops service instead of creating bandwidth overage."
        ),
    )
    summary = InfrastructureCostSummary(
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
        source="Railway + Neon + Resend + retained Azure + Cloudflare R2",
        forecast_monthly_cost_usd=(
            _env_float("INFRA_FORECAST_MONTHLY_COST_USD")
            if env("INFRA_FORECAST_MONTHLY_COST_USD") is not None
            else round(
                sum(item.projected_amount_due_usd or 0 for item in provider_billing)
                + (azure_billing.projected_amount_due_usd or 0),
                2,
            )
        ),
        items=items,
        history=history,
        detail=(
            "The headline is the unpaid current-month amount. Provider actuals are used where "
            "supplied and plan estimates otherwise. Monthly snapshots are retained in the "
            "application database; INFRA_COST_HISTORY_JSON can backfill invoice totals and payments."
        ),
    )
    return summary, azure_billing


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


def infrastructure_dashboard(
    db: Session, *, force_refresh: bool = False
) -> InfrastructureDashboard:
    storage_metrics = [_r2_storage(force_refresh), _database_storage(db)]
    compute_metrics = _compute_metrics()
    connections = _database_connections(db)
    cost_drivers, provider_billing = _provider_usage_dashboard(
        db,
        storage_metrics[0],
        storage_metrics[1],
        force_refresh=force_refresh,
    )
    costs, azure_billing = _cost_summary(
        db,
        provider_billing,
        force_refresh=force_refresh,
    )
    provider_billing.append(azure_billing)
    return InfrastructureDashboard(
        collected_at=datetime.now(timezone.utc),
        refresh_after_seconds=30,
        storage=storage_metrics,
        compute=compute_metrics,
        database_connections=connections,
        quotas=_quota_metrics(),
        cost_drivers=cost_drivers,
        provider_billing=provider_billing,
        costs=costs,
        alerts=_alerts(storage_metrics, compute_metrics, connections, costs),
    )
