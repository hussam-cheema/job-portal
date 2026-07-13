from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

import httpx

from app.config import cfg, env
from app.logging_config import get_logger

logger = get_logger("jobportal.embeddings")

_TITLE_NOISE = {
    "2024",
    "2025",
    "2026",
    "answers",
    "complete",
    "guide",
    "interview",
    "interviews",
    "latest",
    "pakistan",
    "questions",
    "tips",
    "video",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _title_tokens(text: str) -> list[str]:
    tokens = _tokens(text)
    cleaned = [token for token in tokens if token not in _TITLE_NOISE]
    return cleaned or tokens


def embed_text(text: str) -> Counter:
    """Deterministic fallback embedding used when the configured provider is unavailable."""
    toks = _tokens(text)
    grams = list(toks)
    grams.extend(f"{a}_{b}" for a, b in zip(toks, toks[1:]))
    return Counter(grams)


def cosine_similarity(a: Any, b: Any) -> float:
    if isinstance(a, Counter) and isinstance(b, Counter):
        if not a or not b:
            return 0.0
        common = set(a) & set(b)
        if not common:
            return 0.0
        dot = sum(a[t] * b[t] for t in common)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
    else:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(float(x) * float(y) for x, y in zip(a, b))
        na = math.sqrt(sum(float(x) * float(x) for x in a))
        nb = math.sqrt(sum(float(y) * float(y) for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return float(dot / (na * nb))


def text_similarity(a: str, b: str) -> float:
    """Fast local similarity for validation and provider fallback."""
    return cosine_similarity(embed_text(a), embed_text(b))


def _openai_embeddings(texts: list[str]) -> list[list[float]]:
    conf = cfg("embeddings") or {}
    api_key = env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    base_url = (env("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    payload: dict[str, Any] = {
        "model": conf.get("model") or "text-embedding-3-large",
        "input": texts,
    }
    dimensions = conf.get("dimensions")
    if dimensions:
        payload["dimensions"] = int(dimensions)
    response = httpx.post(
        f"{base_url}/embeddings",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=float(conf.get("timeout_seconds") or 30),
    )
    response.raise_for_status()
    rows = sorted(response.json().get("data") or [], key=lambda row: row.get("index", 0))
    if len(rows) != len(texts):
        raise RuntimeError("Embedding provider returned an incomplete batch")
    return [row["embedding"] for row in rows]


def _title_similarity_scores(query: str, titles: list[str]) -> list[float]:
    normalized = [" ".join(_title_tokens(value)) for value in [query, *titles]]
    provider = str((cfg("embeddings") or {}).get("provider") or "openai").lower()
    vectors: list[Any]
    try:
        if provider != "openai":
            raise RuntimeError(f"Unsupported embedding provider: {provider}")
        vectors = _openai_embeddings(normalized)
    except Exception as exc:
        logger.warning("embedding provider unavailable; using local fallback: %s", exc)
        vectors = [embed_text(text) for text in normalized]

    query_tokens = set(_title_tokens(query))
    scores: list[float] = []
    for title, vector in zip(titles, vectors[1:]):
        score = cosine_similarity(vectors[0], vector)
        title_tokens = set(_title_tokens(title))
        # Exact role-title containment remains a strong match despite generic video suffixes.
        if query_tokens and query_tokens.issubset(title_tokens):
            score = max(score, 0.97)
        scores.append(max(0.0, min(1.0, score)))
    return scores


def rank_by_similarity(
    query: str,
    candidates: list[dict],
    key: str = "title",
    score_key: str | None = None,
) -> list[dict]:
    """Rank candidates with the configured large embedding model in one request."""
    if not candidates:
        return []
    scores = _title_similarity_scores(query, [str(c.get(key) or "") for c in candidates])
    scored: list[tuple[float, dict]] = []
    for score, candidate in zip(scores, candidates):
        row = dict(candidate)
        if score_key:
            row[score_key] = round(score, 4)
        scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored]


def answer_matches_question(question: str, answer: str, min_score: float = 0.05) -> bool:
    """Loose local check that answer text relates to the question."""
    if not question or not answer:
        return False
    normalized = answer.strip().lower()
    if normalized in {"see video", "see video.", "n/a", "none", "unknown"}:
        return False
    if len(normalized) < 8:
        return False
    if text_similarity(question, answer) >= min_score:
        return True
    return len(normalized) >= 40
