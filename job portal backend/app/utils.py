from __future__ import annotations

import re
import unicodedata
from html import unescape
from typing import Optional


def slugify(text: str, max_len: int = 120) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return (text or "item")[:max_len].rstrip("-")


def strip_html(html: str, max_len: Optional[int] = None) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_len is not None:
        return text[:max_len]
    return text


def normalize_job_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip().lower()
    if v in {"govt", "government", "gov"}:
        return "government"
    if v in {"private", "company", "newspaper"}:
        return "private"
    return v


def as_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    return []


def experience_label(value: Optional[str]) -> Optional[str]:
    if value is None or str(value).strip() == "":
        return None
    raw = str(value).strip()
    # Accept "3", "3 year(s)", "0-2"
    if re.search(r"year", raw, re.I):
        return raw
    return f"{raw} year(s)"
