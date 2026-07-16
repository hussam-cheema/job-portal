from __future__ import annotations

import base64
import html
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont

from app.config import cfg, watermark_opacity, watermark_text
from app.logging_config import get_logger

logger = get_logger("jobportal.watermark")

WATERMARK_VERSION = "2"

_IMAGE_SRC_RE = re.compile(
    r"(?P<prefix><img\b[^>]*?\bsrc\s*=\s*)(?P<quote>['\"])(?P<src>[^'\"]+)(?P=quote)",
    re.IGNORECASE,
)
_DATA_IMAGE_RE = re.compile(
    r"^data:(?P<mime>image/[a-zA-Z0-9.+-]+);base64,(?P<payload>.+)$",
    re.IGNORECASE | re.DOTALL,
)
_SUPPORTED_DATA_IMAGES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
}


def apply_watermark(
    image_bytes: bytes,
    content_type: Optional[str] = None,
    *,
    strict: bool = False,
) -> bytes:
    """Apply the configured watermark while preserving the raster image format."""
    if not bool(cfg("watermark", "enabled", default=True)):
        return image_bytes

    try:
        source = Image.open(io.BytesIO(image_bytes))
        detected_format = (source.format or "").upper()
        img = source.convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        text = watermark_text() or "PakistanJobs"
        opacity = watermark_opacity()
        alpha = max(0, min(255, int(float(opacity) * 255)))
        color = str(cfg("watermark", "color", default="#FF0000"))
        rgb = _hex_to_rgb(color)

        scale = float(cfg("watermark", "font_scale", default=0.05) or 0.05)
        font_size = max(14, int(img.width * scale))
        font = _load_font(font_size)

        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        max_text_width = max(1, int(img.width * 0.84))
        if tw > max_text_width:
            font_size = max(14, int(font_size * max_text_width / tw))
            font = _load_font(font_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (img.width - tw) // 2
        y = (img.height - th) // 2
        stroke_width = max(1, font_size // 24)
        padding_x = max(8, font_size // 5)
        padding_y = max(5, font_size // 8)
        draw.rounded_rectangle(
            (
                x - padding_x,
                y - padding_y,
                x + tw + padding_x,
                y + th + padding_y,
            ),
            radius=max(4, font_size // 7),
            fill=(0, 0, 0, max(50, alpha // 2)),
        )
        draw.text(
            (x, y),
            text,
            fill=(*rgb, alpha),
            font=font,
            stroke_width=stroke_width,
            stroke_fill=(255, 255, 255, max(120, min(220, alpha + 40))),
        )

        out = Image.alpha_composite(img, overlay)
        buf = io.BytesIO()
        fmt = _output_format(content_type, detected_format)
        save_kwargs: dict[str, object] = {}
        if fmt == "JPEG":
            out = out.convert("RGB")
            save_kwargs["quality"] = 90
        elif fmt == "WEBP":
            save_kwargs["quality"] = 90
        elif fmt == "GIF":
            out = out.convert("P", palette=Image.Palette.ADAPTIVE)
        elif fmt == "BMP":
            out = out.convert("RGB")
        out.save(buf, format=fmt, **save_kwargs)
        return buf.getvalue()
    except Exception:
        logger.exception("watermark failed")
        if strict:
            raise ValueError("Unable to watermark the image") from None
        return image_bytes


def process_description_images(description: str, job_id: str) -> str:
    """Ensure every owned image in a job description has the current watermark.

    Newly uploaded R2 images carry watermark metadata and are left unchanged.
    Embedded data images and legacy R2 objects without the current metadata are
    watermarked, uploaded under a fresh key, and replaced in the saved HTML.
    Arbitrary external URLs are intentionally not downloaded.
    """
    if not description or "<img" not in description.lower():
        return description

    max_mb = float(cfg("r2", "max_image_mb", default=8) or 8)
    max_bytes = int(max_mb * 1024 * 1024)

    def replace(match: re.Match[str]) -> str:
        src = html.unescape(match.group("src"))
        data_match = _DATA_IMAGE_RE.match(src)
        filename: str
        if data_match:
            mime = data_match.group("mime").lower()
            extension = _SUPPORTED_DATA_IMAGES.get(mime)
            if not extension:
                raise ValueError(f"Unsupported embedded image type: {mime}")
            try:
                payload = re.sub(r"\s+", "", data_match.group("payload"))
                raw = base64.b64decode(payload, validate=True)
            except Exception:
                raise ValueError("The job description contains an invalid embedded image") from None
            filename = f"description-{uuid4().hex}{extension}"
        else:
            from app.services.storage import read_public_object

            stored = read_public_object(src, max_bytes=max_bytes)
            if stored is None:
                return match.group(0)
            metadata = {
                str(key).lower(): str(value)
                for key, value in dict(stored.get("metadata") or {}).items()
            }
            if metadata.get("watermark-version") == WATERMARK_VERSION:
                return match.group(0)
            raw = bytes(stored["data"])
            mime = str(stored.get("content_type") or "image/png").split(";", 1)[0].lower()
            extension = _SUPPORTED_DATA_IMAGES.get(mime) or Path(str(stored["filename"])).suffix
            if not extension:
                extension = ".png"
            filename = f"description-{uuid4().hex}{extension}"

        if not raw:
            raise ValueError("The job description contains an empty image")
        if len(raw) > max_bytes:
            raise ValueError(f"Job description image exceeds {max_mb:g}MB")

        data = apply_watermark(raw, mime, strict=True)
        from app.services.storage import upload_bytes

        meta = upload_bytes(
            data,
            filename=filename,
            content_type=mime,
            folder="images",
            job_id=job_id,
            metadata={"watermark-version": WATERMARK_VERSION},
        )
        public_url = html.escape(str(meta["public_url"]), quote=True)
        return f"{match.group('prefix')}{match.group('quote')}{public_url}{match.group('quote')}"

    return _IMAGE_SRC_RE.sub(replace, description)


def migrate_legacy_job_watermarks(db) -> int:
    """Upgrade legacy R2 job-description images once after deployment."""
    from app.models import Job, SiteSetting

    marker_key = f"job_description_watermarks_v{WATERMARK_VERSION}"
    if db.get(SiteSetting, marker_key) is not None:
        return 0

    changed = 0
    failures = 0
    jobs = db.query(Job).filter(Job.description.ilike("%<img%")).all()
    for job in jobs:
        try:
            updated = process_description_images(job.description, job.id)
            if updated != job.description:
                job.description = updated
                job.updated_at = datetime.utcnow()
                changed += 1
        except Exception:
            failures += 1
            logger.exception("legacy watermark migration failed job_id=%s", job.id)

    if failures == 0:
        db.add(SiteSetting(key=marker_key, value=str(changed)))
    else:
        logger.warning(
            "legacy watermark migration incomplete changed=%s failures=%s",
            changed,
            failures,
        )
    return changed


def _output_format(content_type: Optional[str], detected_format: str) -> str:
    ct = (content_type or "").lower()
    if "jpeg" in ct or "jpg" in ct or detected_format == "JPEG":
        return "JPEG"
    if "webp" in ct or detected_format == "WEBP":
        return "WEBP"
    if "gif" in ct or detected_format == "GIF":
        return "GIF"
    if "bmp" in ct or detected_format == "BMP":
        return "BMP"
    return "PNG"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = (value or "#FF0000").lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    try:
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    except Exception:
        return 255, 0, 0


def _load_font(size: int):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if not Path(path).exists():
            continue
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()
