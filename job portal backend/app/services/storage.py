from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlsplit

from app.config import cfg, env, r2_enabled
from app.logging_config import get_logger

logger = get_logger("jobportal.storage")


def _r2_endpoint() -> str:
    explicit = env("R2_ENDPOINT")
    if explicit:
        return explicit.rstrip("/")
    account_id = env("R2_ACCOUNT_ID")
    if not account_id:
        raise RuntimeError("R2_ACCOUNT_ID or R2_ENDPOINT must be configured")
    return f"https://{account_id}.r2.cloudflarestorage.com"


def _r2_client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=_r2_endpoint(),
        region_name="auto",
        aws_access_key_id=env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=env("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version="s3v4"),
    )


def _bucket() -> str:
    return env("R2_BUCKET_NAME") or str(cfg("r2", "bucket") or "")


def _prefix() -> str:
    return str(cfg("r2", "prefix", default="job-portal")).strip("/")


def public_url_for(key: str) -> str:
    base = env("R2_PUBLIC_BASE_URL") or str(cfg("r2", "public_base_url") or "")
    if not base:
        raise RuntimeError(
            "R2_PUBLIC_BASE_URL must be the bucket's public custom domain or r2.dev URL"
        )
    return f"{base.rstrip('/')}/{key.lstrip('/')}"


def _build_key(*, job_id: str | None, kind: str, filename: str) -> str:
    """
    R2 object layout:
      job-portal/{job_uuid}/images/{uuid}.ext
      job-portal/{job_uuid}/attachments/{uuid}.ext
      job-portal/pending/{uuid}/...   when job not yet created
    """
    ext = Path(filename).suffix.lower() or ""
    file_id = uuid.uuid4().hex
    if kind == "branding":
        return f"{_prefix()}/branding/{file_id}{ext}"
    folder = "images" if kind == "images" else "attachments"
    job_folder = job_id or f"pending/{uuid.uuid4().hex}"
    return f"{_prefix()}/{job_folder}/{folder}/{file_id}{ext}"


def upload_bytes(
    data: bytes,
    *,
    filename: str,
    content_type: Optional[str] = None,
    folder: str = "files",
    job_id: Optional[str] = None,
    metadata: Optional[dict[str, str]] = None,
) -> dict:
    """Upload to Cloudflare R2 under the job UUID folder."""
    try:
        kind = "branding" if folder == "branding" else (
            "images" if folder in {"images", "image"} else "attachments"
        )
        if folder not in {"images", "image", "attachments", "files", "branding"}:
            kind = "attachments" if "attach" in folder else "images"

        key = _build_key(job_id=job_id, kind=kind, filename=filename)
        ctype = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

        if not (
            r2_enabled()
            and _bucket()
            and env("R2_ACCESS_KEY_ID")
            and env("R2_SECRET_ACCESS_KEY")
        ):
            raise RuntimeError(
                "R2 is required. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
                "R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_PUBLIC_BASE_URL "
                "and R2_ENABLED=true"
            )

        client = _r2_client()
        try:
            client.put_object(
                Bucket=_bucket(),
                Key=key,
                Body=data,
                ContentType=ctype,
                Metadata=metadata or {},
            )
        except Exception:
            logger.exception("r2 put_object failed key=%s", key)
            raise

        url = public_url_for(key)
        logger.info("r2_upload ok key=%s size=%s job_id=%s", key, len(data), job_id)
        return {
            # Retained for API/database compatibility with existing deployments.
            "s3_path": key,
            "public_url": url,
            "file_type": ctype,
            "file_size": len(data),
            "original_name": filename,
            "storage": "r2",
        }
    except Exception:
        logger.exception("upload_bytes failed")
        raise


def read_public_object(
    public_url: str,
    *,
    max_bytes: int,
) -> Optional[dict[str, object]]:
    """Read an object only when the URL belongs to this application's R2 bucket.

    This deliberately refuses arbitrary remote URLs so job-description processing
    cannot be used as a server-side request forgery proxy.
    """
    base = env("R2_PUBLIC_BASE_URL") or str(cfg("r2", "public_base_url") or "")
    if not base or not public_url:
        return None

    base_parts = urlsplit(base.rstrip("/"))
    url_parts = urlsplit(public_url)
    if (
        url_parts.scheme.lower() != base_parts.scheme.lower()
        or url_parts.netloc.lower() != base_parts.netloc.lower()
    ):
        return None

    base_path = base_parts.path.rstrip("/")
    object_path = url_parts.path
    expected_prefix = f"{base_path}/" if base_path else "/"
    if not object_path.startswith(expected_prefix):
        return None
    key = unquote(object_path[len(expected_prefix) :]).lstrip("/")
    if not key or not key.startswith(f"{_prefix()}/"):
        return None

    response = _r2_client().get_object(Bucket=_bucket(), Key=key)
    body = response["Body"]
    data = body.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("Stored image exceeds the configured image size limit")
    return {
        "data": data,
        "content_type": response.get("ContentType") or mimetypes.guess_type(key)[0],
        "metadata": response.get("Metadata") or {},
        "key": key,
        "filename": Path(key).name,
    }


def read_public_image_key(
    object_key: str,
    *,
    max_bytes: int,
) -> dict[str, object]:
    """Read a public job-description image from R2 by object key.

    The public media endpoint uses this helper as a delivery fallback when a
    browser cannot load the bucket's public hostname directly.  Only image
    objects inside this application's prefix are accepted; attachments and
    arbitrary R2 keys remain inaccessible through the endpoint.
    """
    key = unquote(object_key).lstrip("/")
    prefix = f"{_prefix()}/"
    suffix = Path(key).suffix.lower()
    allowed_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
    if (
        not key.startswith(prefix)
        or ".." in Path(key).parts
        or suffix not in allowed_extensions
        or ("/images/" not in key and "/branding/" not in key)
    ):
        raise ValueError("Invalid public image key")

    response = _r2_client().get_object(Bucket=_bucket(), Key=key)
    data = response["Body"].read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("Stored image exceeds the configured image size limit")
    return {
        "data": data,
        "content_type": response.get("ContentType") or mimetypes.guess_type(key)[0],
        "key": key,
    }


def resolve_local_path(object_path: str) -> Optional[Path]:
    """Local media serving is disabled when using R2-only storage."""
    return None
