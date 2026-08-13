#!/usr/bin/env python3
from __future__ import annotations

import os
import time

from common import BACKEND_DIR, CheckFailed, add_backend_to_path, run


def check() -> str:
    model_root = BACKEND_DIR / ".model-cache"
    model_path = model_root / "Qwen3-Embedding-0.6B-Q8_0.gguf"
    os.environ["EMBEDDING_PROVIDER"] = "qwen3"
    os.environ["QWEN3_EMBEDDING_MODEL_PATH"] = str(model_path)
    os.environ["QWEN3_EMBEDDING_MODEL_MOUNT_PATH"] = str(model_root)
    os.environ["QWEN3_EMBEDDING_REQUIRE_PERSISTENT_STORAGE"] = "false"
    os.environ["QWEN3_EMBEDDING_THREADS"] = "1"
    add_backend_to_path()

    from app.config import cfg
    from app.services.embeddings import rank_by_similarity
    from app.services.model_cache import ensure_local_embedding_model

    started = time.monotonic()
    ensure_local_embedding_model()
    ranked = rank_by_similarity(
        "FIA Inspector jobs in government",
        [
            {"title": "Interviews for Government Jobs in Pakistan"},
            {"title": "FIA Sub Inspector Interview Experience and Questions"},
            {"title": "FIA Inspector ki age limit aur test pattern"},
        ],
        score_key="similarity",
    )
    if not ranked or "fia" not in ranked[0]["title"].lower():
        raise CheckFailed(f"Qwen3 ranked an unrelated title first: {ranked}")
    if not 0 <= float(ranked[0]["similarity"]) <= 1:
        raise CheckFailed(f"Invalid cosine similarity: {ranked[0]}")
    configured_threshold = float(
        cfg("youtube_qna", "min_title_similarity", default=0.80)
    )
    matched = [
        row for row in ranked if float(row["similarity"]) >= configured_threshold
    ]
    if len(matched) < 2:
        raise CheckFailed(
            f"Expected English/Roman-Urdu FIA matches at configured "
            f"min_title_similarity={configured_threshold}: {ranked}"
        )
    scores = ", ".join(f"{row['similarity']:.4f} {row['title']}" for row in ranked)
    return (
        f"Official Qwen/Qwen3-Embedding-0.6B Q8 loaded from {model_path}; "
        f"ranked multilingual FIA titles in {time.monotonic() - started:.2f}s "
        f"(min_title_similarity={configured_threshold}): {scores}"
    )


if __name__ == "__main__":
    raise SystemExit(run(check))
