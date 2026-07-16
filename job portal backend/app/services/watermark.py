from __future__ import annotations

import base64
import html
import io
import re
from pathlib import Path
from typing import Optional
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont

from app.config import cfg, watermark_opacity, watermark_text
from app.logging_config import get_logger

logger = get_logger("jobportal.watermark")

_DATA_IMAGE_RE = re.compile(
    r"(?P<prefix><img\b[^>]*?\bsrc\s*=\s*)(?P<quote>['\"])(?P<src>data:(?P<mime>image/[a-zA-Z0-9.+-]+);base64,(?P<payload>[^'\"]+))(?P=quote)",
    re.IGNORECASE,
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
        x = (img.width - tw) // 2
        y = (img.height - th) // 2
        stroke_width = max(1, font_size // 24)
        draw.text(
            (x, y),
            text,
            fill=(*rgb, alpha),
            font=font,
            stroke_width=stroke_width,
            stroke_fill=(255, 255, 255, max(1, alpha // 2)),
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
    """Persist and watermark images pasted directly into the job description.

    Images selected through the editor uploader already have an R2 URL and were
    watermarked by the upload endpoint. Rich-text editors may instead embed a
    pasted image as a data URL; those images are handled here before saving.
    """
    if not description or "data:image/" not in description.lower():
        return description

    max_mb = float(cfg("r2", "max_image_mb", default=8) or 8)
    max_bytes = int(max_mb * 1024 * 1024)

    def replace(match: re.Match[str]) -> str:
        mime = match.group("mime").lower()
        extension = _SUPPORTED_DATA_IMAGES.get(mime)
        if not extension:
            raise ValueError(f"Unsupported embedded image type: {mime}")
        try:
            payload = re.sub(r"\s+", "", match.group("payload"))
            raw = base64.b64decode(payload, validate=True)
        except Exception:
            raise ValueError("The job description contains an invalid embedded image") from None
        if not raw:
            raise ValueError("The job description contains an empty embedded image")
        if len(raw) > max_bytes:
            raise ValueError(f"Embedded image exceeds {max_mb:g}MB")

        data = apply_watermark(raw, mime, strict=True)
        from app.services.storage import upload_bytes

        filename = f"description-{uuid4().hex}{extension}"
        meta = upload_bytes(
            data,
            filename=filename,
            content_type=mime,
            folder="images",
            job_id=job_id,
        )
        public_url = html.escape(str(meta["public_url"]), quote=True)
        return f"{match.group('prefix')}{match.group('quote')}{public_url}{match.group('quote')}"

    return _DATA_IMAGE_RE.sub(replace, description)


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
