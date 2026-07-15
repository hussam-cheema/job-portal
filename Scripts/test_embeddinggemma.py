#!/usr/bin/env python3
from __future__ import annotations

import os
import time

from common import BACKEND_DIR, CheckFailed, add_backend_to_path, run


def check() -> str:
    model_root = BACKEND_DIR / ".model-cache"
    model_path = model_root / "embeddinggemma-300M-qat-Q4_0.gguf"
    os.environ["EMBEDDING_PROVIDER"] = "embeddinggemma"
    os.environ["EMBEDDINGGEMMA_MODEL_PATH"] = str(model_path)
    os.environ["EMBEDDINGGEMMA_MODEL_MOUNT_PATH"] = str(model_root)
    os.environ["EMBEDDINGGEMMA_REQUIRE_PERSISTENT_STORAGE"] = "false"
    os.environ["EMBEDDINGGEMMA_THREADS"] = "1"
    add_backend_to_path()

    from app.services.embeddings import rank_by_similarity
    from app.services.model_cache import ensure_local_embedding_model
    from app.config import cfg

    started = time.monotonic()
    ensure_local_embedding_model()
    ranked = rank_by_similarity(
        "FIA Inspector jobs in government",
        [
            {"title": "Interviews for Government Jobs in Pakistan"},
            {"title": "FIA Sub Inspector Interview Experience and Questions"},
            {"title": "FIA written paper result and interview questions"},
        ],
        score_key="similarity",
    )
    if not ranked or not ranked[0]["title"].startswith("FIA"):
        raise CheckFailed(f"EmbeddingGemma ranked an unrelated title first: {ranked}")
    if not 0 <= float(ranked[0]["similarity"]) <= 1:
        raise CheckFailed(f"Invalid cosine similarity: {ranked[0]}")
    configured_threshold = float(
        cfg("youtube_qna", "min_title_similarity", default=0.95)
    )
    if float(ranked[0]["similarity"]) < configured_threshold:
        raise CheckFailed(
            f"Best FIA match {ranked[0]['similarity']} is below configured "
            f"min_title_similarity={configured_threshold}"
        )
    scores = ", ".join(f"{row['similarity']:.4f} {row['title']}" for row in ranked)
    return (
        f"Quantized google/embeddinggemma-300m loaded from {model_path}; "
        f"ranked FIA titles with cosine similarity in {time.monotonic() - started:.2f}s "
        f"(min_title_similarity={configured_threshold}): {scores}"
    )


if __name__ == "__main__":
    raise SystemExit(run(check))
