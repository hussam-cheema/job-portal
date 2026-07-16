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

    args.output.parent.mkdir(parents=True, exist_ok=True)
    outputs = [args.output, args.output.with_name(f"{args.output.stem}-dark{args.output.suffix}")]
    for source_color, output in zip(((242, 245, 248), (20, 25, 31)), outputs):
        source = Image.new("RGB", (1200, 630), color=source_color)
        source_buffer = io.BytesIO()
        source.save(source_buffer, format="PNG")
        result = apply_watermark(source_buffer.getvalue(), "image/png", strict=True)

        try:
            rendered = Image.open(io.BytesIO(result)).convert("RGB")
        except Exception as exc:
            raise CheckFailed(f"watermark output is not a valid image: {exc}") from exc
        if rendered.size != source.size:
            raise CheckFailed(f"watermark changed image dimensions to {rendered.size}")
        difference = ImageChops.difference(source, rendered)
        visibly_changed = sum(
            1 for pixel in difference.get_flattened_data() if max(pixel) >= 16
        )
        minimum_visible_pixels = int(source.width * source.height * 0.005)
        if visibly_changed < minimum_visible_pixels:
            raise CheckFailed(
                "watermark exists only as an imperceptible pixel change "
                f"({visibly_changed} visible pixels; need {minimum_visible_pixels})"
            )
        output.write_bytes(result)
    return f"visible watermarks verified on light and dark images: {outputs[0]}, {outputs[1]}"


if __name__ == "__main__":
    raise SystemExit(run(check))
