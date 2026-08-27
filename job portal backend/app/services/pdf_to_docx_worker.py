"""Isolated PDF-to-DOCX worker invoked by the conversion job manager."""

from __future__ import annotations

import sys
from pathlib import Path

from pdf2docx import Converter


def main() -> int:
    if len(sys.argv) != 3:
        return 2
    source = Path(sys.argv[1]).resolve()
    destination = Path(sys.argv[2]).resolve()
    if source.suffix.lower() != ".pdf" or destination.suffix.lower() != ".docx":
        return 2

    converter = Converter(str(source))
    try:
        converter.convert(str(destination))
    finally:
        converter.close()
    return 0 if destination.is_file() and destination.stat().st_size > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
