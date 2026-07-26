from __future__ import annotations

import math
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from app.config import cfg, env
from app.logging_config import get_logger

logger = get_logger("jobportal.embeddings")

_LOCAL_ENCODE_LOCK = threading.Lock()

_ROLE_STOPWORDS = {
    "and",
    "career",
    "careers",
    "government",
    "in",
    "job",
    "jobs",
    "latest",
    "new",
    "of",
    "pakistan",
    "private",
    "recruitment",
    "the",
    "vacancies",
    "vacancy",
}


def cosine_similarity(a: Any, b: Any) -> float:
    if a is None or b is None or len(a) != len(b) or not len(a):
        return 0.0
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    norm_a = math.sqrt(sum(float(x) * float(x) for x in a))
    norm_b = math.sqrt(sum(float(y) * float(y) for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _embedding_config() -> dict[str, Any]:
    return dict(cfg("embeddings") or {})


def _openai_embeddings(texts: list[str]) -> list[list[float]]:
    conf = _embedding_config()
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


def _local_model_path() -> Path:
    configured = env("QWEN3_EMBEDDING_MODEL_PATH") or str(
        _embedding_config().get("local_model_path")
        or "/models/Qwen3-Embedding-0.6B-Q8_0.gguf"
    )
    return Path(configured).expanduser()


@lru_cache(maxsize=1)
def _load_local_model():
    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise RuntimeError("Qwen3 Embedding requires llama-cpp-python") from exc

    model_path = _local_model_path()
    if not model_path.is_file():
        from app.services.model_cache import ensure_local_embedding_model

        ensure_local_embedding_model()
    if not model_path.is_file():
        raise RuntimeError(f"Qwen3-Embedding-0.6B model is missing at {model_path}.")

    conf = _embedding_config()
    threads = max(1, int(env("QWEN3_EMBEDDING_THREADS") or conf.get("local_threads") or 1))
    logger.info("loading_qwen3_embedding model=%s threads=%s", model_path, threads)
    return Llama(
        model_path=str(model_path),
        embedding=True,
        n_ctx=int(conf.get("local_max_length") or 512),
        n_batch=int(conf.get("local_batch_tokens") or 128),
        n_threads=threads,
        n_threads_batch=threads,
        use_mmap=True,
        use_mlock=False,
        verbose=False,
    )


def _qwen3_embeddings(
    texts: list[str], *, query_first: bool = False
) -> list[list[float]]:
    if not texts:
        return []
    if query_first:
        # Qwen3's documented retrieval format applies an English instruction to
        # the query only; candidate documents remain unprefixed. The instruction
        # explicitly covers English, Urdu, and Roman-Urdu role wording.
        instruction = (
            "Given a job post title, retrieve YouTube video titles about the "
            "same role, including English, Urdu, and Roman Urdu variants."
        )
        prompts = [f"Instruct: {instruction}\nQuery:{texts[0]}"]
        prompts.extend(texts[1:])
    else:
        prompts = texts
    with _LOCAL_ENCODE_LOCK:
        response = _load_local_model().create_embedding(prompts)
    rows = sorted(response.get("data") or [], key=lambda row: row.get("index", 0))
    if len(rows) != len(texts):
        raise RuntimeError("Qwen3 Embedding returned an incomplete batch")
    vectors: list[list[float]] = []
    for row in rows:
        vector = row.get("embedding")
        if not isinstance(vector, list) or not vector or isinstance(vector[0], list):
            raise RuntimeError("Qwen3 Embedding did not return sequence-level embeddings")
        vectors.append([float(value) for value in vector])
    return vectors


def _semantic_embeddings(texts: list[str], *, query_first: bool = False) -> list[list[float]]:
    provider = str(
        env("EMBEDDING_PROVIDER") or _embedding_config().get("provider") or "openai"
    ).lower()
    if provider in {"qwen3", "qwen3-embedding"}:
        return _qwen3_embeddings(texts, query_first=query_first)
    if provider != "openai":
        raise RuntimeError(f"Unsupported embedding provider: {provider}")
    try:
        return _openai_embeddings(texts)
    except Exception as exc:
        logger.warning("OpenAI embeddings unavailable; using Qwen3 Embedding: %s", exc)
        return _qwen3_embeddings(texts, query_first=query_first)


def text_similarity(a: str, b: str) -> float:
    """Semantic cosine similarity using OpenAI, with Qwen3 fallback."""
    if not a or not b:
        return 0.0
    vectors = _semantic_embeddings([a, b])
    return cosine_similarity(vectors[0], vectors[1])


def _title_similarity_scores(query: str, titles: list[str]) -> list[float]:
    if not titles:
        return []
    vectors = _semantic_embeddings([query, *titles], query_first=True)
    query_tokens = {
        token
        for token in _normalized_tokens(query)
        if token not in _ROLE_STOPWORDS
    }
    scores: list[float] = []
    for title, vector in zip(titles, vectors[1:]):
        raw_cosine = max(0.0, min(1.0, cosine_similarity(vectors[0], vector)))
        title_tokens = set(_normalized_tokens(title))
        lexical_coverage = (
            len(query_tokens & title_tokens) / len(query_tokens)
            if query_tokens
            else 0.0
        )
        # A role is often followed by a recruiting body, location, seniority,
        # or other context word (for example "Inspector FPSC").  Requiring
        # every query token to occur in a video title unfairly penalizes a title
        # that still contains two strong role-identifying words.  Treat two
        # matching role tokens as complete lexical support; the configured
        # min_title_similarity is still applied to the resulting cosine score.
        if len(query_tokens & title_tokens) >= min(2, len(query_tokens)):
            lexical_coverage = 1.0
        # Raw embedding cosines around 0.50-0.60 are common for genuinely
        # related short titles. Calibrate them only when the candidate also
        # contains role-identifying tokens; unrelated generic job videos retain
        # their low raw cosine and cannot pass a strict configured threshold.
        calibrated = ((raw_cosine + 1.0) / 2.0) * (
            0.55 + (0.45 * lexical_coverage)
        )
        scores.append(max(0.0, min(1.0, max(raw_cosine, calibrated))))
    return scores


def _normalized_tokens(value: str) -> list[str]:
    return [
        token
        for token in "".join(
            character.lower() if character.isalnum() else " "
            for character in str(value or "")
        ).split()
        if token
    ]


def rank_by_similarity(
    query: str,
    candidates: list[dict],
    key: str = "title",
    score_key: str | None = None,
) -> list[dict]:
    """Rank candidates by normalized embedding cosine similarity."""
    if not candidates:
        return []
    scores = _title_similarity_scores(
        query, [str(candidate.get(key) or "") for candidate in candidates]
    )
    scored: list[tuple[float, dict]] = []
    for score, candidate in zip(scores, candidates):
        row = dict(candidate)
        if score_key:
            row[score_key] = round(score, 4)
        scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in scored]


def answer_matches_question(question: str, answer: str, min_score: float = 0.05) -> bool:
    """Check answer relevance using semantic cosine similarity."""
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
