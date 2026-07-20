from __future__ import annotations

import logging
import os
import queue
import re
import socket
import sys
import tempfile
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo


PKT = ZoneInfo("Asia/Karachi")
DEFAULT_MAX_BYTES = 100 * 1024 * 1024
_STOP = object()
_BLOCKED_LOGGER_PREFIXES = ("boto", "botocore", "s3transfer", "urllib3")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def r2_production_logging_enabled() -> bool:
    return (
        _env_bool("R2_LOGS_ENABLED")
        and os.getenv("APP_ENV", "").strip().lower() == "production"
    )


def _positive_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-._")
    return cleaned[:80] or "backend"


class PakistanTimeFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        current = datetime.fromtimestamp(record.created, tz=PKT)
        if datefmt:
            return current.strftime(datefmt)
        return current.isoformat(timespec="seconds")


@dataclass(frozen=True)
class _LogItem:
    line: str
    created_at: datetime


class R2ProductionLogHandler(logging.Handler):
    """Persist high-value production logs to Cloudflare R2.

    The handler deliberately excludes ordinary INFO/WARNING traffic. It stores
    application errors (including ``logger.exception`` tracebacks) and INFO
    records explicitly marked with ``extra={"r2_lifecycle": True}``.

    R2 objects cannot be appended to, so the current local spool file is
    uploaded as an overwrite after every accepted record. Errors are rare, and
    this gives substantially better durability than waiting for a large batch.
    """

    def __init__(
        self,
        *,
        client_factory: Optional[Callable[[], object]] = None,
        bucket: Optional[str] = None,
        prefix: Optional[str] = None,
        max_bytes: Optional[int] = None,
        retention_days: Optional[int] = None,
        spool_dir: Optional[Path] = None,
        use_background_thread: bool = True,
    ) -> None:
        super().__init__(level=logging.NOTSET)
        self.client_factory = client_factory or self._default_client
        self.bucket = (bucket or os.getenv("R2_BUCKET_NAME", "")).strip()
        self.prefix = (prefix or os.getenv("R2_LOG_PREFIX", "production-logs")).strip("/")
        self.max_bytes = max_bytes or _positive_int("R2_LOG_MAX_BYTES", DEFAULT_MAX_BYTES)
        self.retention_days = retention_days or _positive_int("R2_LOG_RETENTION_DAYS", 2)
        self.use_background_thread = use_background_thread
        self._client: object | None = None
        self._date: str | None = None
        self._cleanup_completed_for: str | None = None
        self._index = 1
        self._current_size = 0
        self._current_path: Path | None = None
        self._closed = False
        self._queue: queue.Queue[_LogItem | object] = queue.Queue(maxsize=2_000)
        self._lock = threading.RLock()
        base_spool = spool_dir or Path(tempfile.gettempdir()) / "job-portal-r2-logs"
        self._spool_dir = Path(base_spool)
        self._spool_dir.mkdir(parents=True, exist_ok=True)
        instance_hint = (
            os.getenv("CONTAINER_APP_REVISION")
            or os.getenv("HOSTNAME")
            or socket.gethostname()
        )
        self._instance = _safe_segment(
            f"{instance_hint}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        )
        self.setFormatter(
            PakistanTimeFormatter(
                "%(asctime)s PKT | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        self._thread: threading.Thread | None = None
        if use_background_thread:
            self._thread = threading.Thread(
                target=self._worker,
                name="r2-production-log-uploader",
                daemon=True,
            )
            self._thread.start()

    @staticmethod
    def _default_client() -> object:
        # Imported lazily to avoid a logging_config -> storage -> logging_config
        # cycle while the application module graph is starting.
        from app.services.storage import _r2_client

        return _r2_client()

    def _should_store(self, record: logging.LogRecord) -> bool:
        if record.name.startswith(_BLOCKED_LOGGER_PREFIXES):
            return False
        return record.levelno >= logging.ERROR or bool(
            getattr(record, "r2_lifecycle", False)
        )

    def emit(self, record: logging.LogRecord) -> None:
        if self._closed or not self._should_store(record):
            return
        try:
            created_at = datetime.fromtimestamp(record.created, tz=PKT)
            item = _LogItem(line=f"{self.format(record)}\n", created_at=created_at)
            if self.use_background_thread:
                self._queue.put_nowait(item)
            else:
                self._write_item(item)
        except queue.Full:
            self._internal_error("R2 production log queue is full; dropping one record")
        except Exception:
            self.handleError(record)

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is _STOP:
                    return
                self._write_item(item)  # type: ignore[arg-type]
            except Exception as exc:
                self._internal_error(f"R2 production log upload failed: {exc}")
            finally:
                self._queue.task_done()

    def _get_client(self) -> object:
        if self._client is None:
            self._client = self.client_factory()
        return self._client

    def _ensure_file(self, current: datetime) -> None:
        current_date = current.astimezone(PKT).date().isoformat()
        if self._date == current_date and self._current_path is not None:
            self._try_cleanup(current, current_date)
            return
        if self._current_path is not None:
            self._upload_current()
            self._remove_current_spool()
        self._date = current_date
        self._index = 1
        self._current_size = 0
        self._current_path = self._spool_dir / (
            f"{current_date}-{self._instance}-{self._index:04d}.log"
        )
        self._try_cleanup(current, current_date)

    def _try_cleanup(self, current: datetime, current_date: str) -> None:
        if self._cleanup_completed_for == current_date:
            return
        try:
            self._cleanup_expired(current)
            self._cleanup_completed_for = current_date
        except Exception as exc:
            # Retention failure must never prevent a new error from being
            # archived. A later accepted record retries cleanup for this date.
            self._internal_error(f"R2 production log retention failed: {exc}")

    def _write_item(self, item: _LogItem) -> None:
        with self._lock:
            self._ensure_file(item.created_at)
            payload = item.line.encode("utf-8", errors="replace")
            offset = 0
            while offset < len(payload):
                available = self.max_bytes - self._current_size
                if available <= 0:
                    self._rotate()
                    available = self.max_bytes
                chunk = payload[offset : offset + available]
                assert self._current_path is not None
                with self._current_path.open("ab") as spool:
                    spool.write(chunk)
                    spool.flush()
                self._current_size += len(chunk)
                offset += len(chunk)
                self._upload_current()
                if self._current_size >= self.max_bytes and offset < len(payload):
                    self._rotate()

    def _rotate(self) -> None:
        self._upload_current()
        self._remove_current_spool()
        self._index += 1
        self._current_size = 0
        assert self._date is not None
        self._current_path = self._spool_dir / (
            f"{self._date}-{self._instance}-{self._index:04d}.log"
        )

    def _object_key(self) -> str:
        assert self._date is not None
        return (
            f"{self.prefix}/{self._date}/"
            f"backend-{self._instance}-{self._index:04d}.log"
        )

    def _upload_current(self) -> None:
        if not self.bucket:
            raise RuntimeError("R2_BUCKET_NAME is required for production logging")
        if self._current_path is None or not self._current_path.exists():
            return
        body = self._current_path.read_bytes()
        if not body:
            return
        self._get_client().put_object(  # type: ignore[attr-defined]
            Bucket=self.bucket,
            Key=self._object_key(),
            Body=body,
            ContentType="text/plain; charset=utf-8",
            Metadata={
                "service": "job-portal-backend",
                "timezone": "Asia-Karachi",
                "retention-days": str(self.retention_days),
            },
        )

    def _cleanup_expired(self, current: datetime) -> None:
        if not self.bucket or not self.prefix:
            return
        keep_from = current.astimezone(PKT).date() - timedelta(
            days=self.retention_days - 1
        )
        token: str | None = None
        expired: list[dict[str, str]] = []
        while True:
            kwargs: dict[str, object] = {
                "Bucket": self.bucket,
                "Prefix": f"{self.prefix}/",
            }
            if token:
                kwargs["ContinuationToken"] = token
            response = self._get_client().list_objects_v2(**kwargs)  # type: ignore[attr-defined]
            for obj in response.get("Contents", []):
                key = str(obj.get("Key", ""))
                relative = key[len(self.prefix) + 1 :]
                date_segment = relative.split("/", 1)[0]
                try:
                    object_date = datetime.strptime(date_segment, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if object_date < keep_from:
                    expired.append({"Key": key})
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")
            if not token:
                break
        for start in range(0, len(expired), 1_000):
            self._get_client().delete_objects(  # type: ignore[attr-defined]
                Bucket=self.bucket,
                Delete={"Objects": expired[start : start + 1_000], "Quiet": True},
            )

    def _remove_current_spool(self) -> None:
        if self._current_path is not None:
            self._current_path.unlink(missing_ok=True)

    @staticmethod
    def _internal_error(message: str) -> None:
        # Never route handler failures back through logging: that could recurse
        # while the handler is already failing to reach R2.
        try:
            sys.stderr.write(f"{message}\n")
        except Exception:
            pass

    def flush(self) -> None:
        if self._closed:
            return
        if self.use_background_thread:
            self._queue.join()
        with self._lock:
            try:
                self._upload_current()
            except Exception as exc:
                self._internal_error(f"R2 production log flush failed: {exc}")

    def close(self) -> None:
        if self._closed:
            return
        self.flush()
        if self.use_background_thread and self._thread is not None:
            self._queue.put(_STOP)
            self._thread.join(timeout=10)
        with self._lock:
            self._remove_current_spool()
        self._closed = True
        super().close()
