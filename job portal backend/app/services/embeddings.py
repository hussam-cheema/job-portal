from __future__ import annotations

import math
import re
from collections import Counter
from difflib import SequenceMatcher
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
    "govt",
    "government",
    "hiring",
    "in",
    "interview",
    "interviews",
    "job",
    "jobs",
    "latest",
    "of",
    "opening",
    "openings",
    "pakistan",
    "preparation",
    "preparations",
    "questions",
    "recruitment",
    "related",
    "the",
    "tips",
    "vacancies",
    "vacancy",
    "video",
    "with",
}


def _tokens(text: str) -> list[str]:
    # Keep dotted acronyms such as F.I.A equivalent to FIA before tokenizing.
    normalized = re.sub(
        r"\b(?:[A-Za-z]\.){2,}[A-Za-z]?\.?",
        lambda match: re.sub(r"[^A-Za-z]", "", match.group(0)),
        text or "",
    )
    return re.findall(r"[a-z0-9]+", normalized.lower())


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
    query_acronyms = {
        token.lower()
        for token in re.findall(r"\b[A-Z][A-Z0-9]{1,7}\b", query or "")
    }
    scores: list[float] = []
    for title, vector in zip(titles, vectors[1:]):
        semantic_score = cosine_similarity(vectors[0], vector)
        title_tokens = set(_title_tokens(title))
        common = query_tokens & title_tokens
        coverage = len(common) / len(query_tokens) if query_tokens else 0.0
        precision = len(common) / len(title_tokens) if title_tokens else 0.0
        token_f1 = (
            2 * coverage * precision / (coverage + precision)
            if coverage and precision
            else 0.0
        )
        query_normalized = " ".join(_title_tokens(query))
        title_normalized = " ".join(_title_tokens(title))
        sequence_score = SequenceMatcher(None, query_normalized, title_normalized).ratio()
        lexical_score = 0.7 * coverage + 0.2 * token_f1 + 0.1 * sequence_score

        # Exact core-role containment is a strong match despite words such as
        # "Sub" or generic interview/preparation suffixes in a YouTube title.
        if query_tokens and query_tokens.issubset(title_tokens):
            lexical_score = max(lexical_score, 0.97)

        score = max(semantic_score, lexical_score)
        # Acronyms identify organisations (FIA, NAB, PPSC, FPSC, etc.). A
        # semantic model must not rank a generic government-job video above a
        # title that actually contains the requested organisation.
        if query_acronyms and not query_acronyms.issubset(title_tokens):
            score = min(score, 0.24)
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
