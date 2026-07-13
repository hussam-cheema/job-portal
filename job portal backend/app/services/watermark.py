from __future__ import annotations

import io
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from app.config import cfg, watermark_opacity, watermark_text
from app.logging_config import get_logger

logger = get_logger("jobportal.watermark")


def apply_watermark(image_bytes: bytes, content_type: Optional[str] = None) -> bytes:
    """Apply red centered watermark at configured opacity. Returns PNG/JPEG bytes."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        text = watermark_text() or "PakJobs"
        opacity = watermark_opacity()
        alpha = max(0, min(255, int(float(opacity) * 255)))
        color = str(cfg("watermark", "color", default="#FF0000"))
        rgb = _hex_to_rgb(color)

        # Font size ~5% of width
        scale = float(cfg("watermark", "font_scale", default=0.05) or 0.05)
        font_size = max(14, int(img.width * scale))
        font = _load_font(font_size)

        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (img.width - tw) // 2
        y = (img.height - th) // 2
        draw.text((x, y), text, fill=(*rgb, alpha), font=font)

        out = Image.alpha_composite(img, overlay)
        buf = io.BytesIO()
        fmt = "PNG"
        ct = (content_type or "").lower()
        if "jpeg" in ct or "jpg" in ct:
            fmt = "JPEG"
            out = out.convert("RGB")
        out.save(buf, format=fmt, quality=90)
        return buf.getvalue()
    except Exception:
        logger.exception("watermark failed — returning original image")
        return image_bytes


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
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()
