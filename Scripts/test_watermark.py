#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image, ImageChops

from common import CheckFailed, SCRIPT_DIR, add_backend_to_path, run


def check() -> str:
    parser = argparse.ArgumentParser(description="Test the configured image watermark service.")
    parser.add_argument("--output", type=Path, default=SCRIPT_DIR / "output" / "watermark-test.png")
    args = parser.parse_args()

    add_backend_to_path()
    from app.services.watermark import apply_watermark

    source = Image.new("RGB", (1200, 630), color=(242, 245, 248))
    source_buffer = io.BytesIO()
    source.save(source_buffer, format="PNG")
    result = apply_watermark(source_buffer.getvalue(), "image/png")

    try:
        rendered = Image.open(io.BytesIO(result)).convert("RGB")
    except Exception as exc:
        raise CheckFailed(f"watermark output is not a valid image: {exc}") from exc
    if rendered.size != source.size:
        raise CheckFailed(f"watermark changed image dimensions to {rendered.size}")
    if ImageChops.difference(source, rendered).getbbox() is None:
        raise CheckFailed("watermark output is pixel-identical to the source image")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    return f"watermark changed the image and wrote {args.output}"


if __name__ == "__main__":
    raise SystemExit(run(check))
