from __future__ import annotations

import os
from pathlib import Path

from filelock import FileLock
from huggingface_hub import hf_hub_download

from app.config import cfg, env
from app.logging_config import get_logger, setup_logging

logger = get_logger("jobportal.model_cache")


def _persistent_storage_required() -> bool:
    return (env("QWEN3_EMBEDDING_REQUIRE_PERSISTENT_STORAGE") or "false").lower() in {
        "1",
        "true",
        "yes",
    }


def _local_fallback_is_needed() -> bool:
    provider = str(
        env("EMBEDDING_PROVIDER")
        or cfg("embeddings", "provider", default="openai")
        or "openai"
    ).lower()
    fallback_provider = str(
        cfg("embeddings", "fallback_provider", default="qwen3")
        or "qwen3"
    ).lower()
    return provider in {"qwen3", "qwen3-embedding"} or fallback_provider in {
        "qwen3",
        "qwen3-embedding",
    }


def ensure_local_embedding_model() -> Path | None:
    if not _local_fallback_is_needed():
        logger.info("Qwen3 Embedding is not the configured provider or fallback")
        return None

    model_path = Path(
        env("QWEN3_EMBEDDING_MODEL_PATH")
        or str(
            cfg(
                "embeddings",
                "local_model_path",
                default="/models/Qwen3-Embedding-0.6B-Q8_0.gguf",
            )
        )
    ).expanduser()
    mount_path = Path(env("QWEN3_EMBEDDING_MODEL_MOUNT_PATH") or "/models")
    if _persistent_storage_required() and not os.path.ismount(mount_path):
        raise RuntimeError(
            f"{mount_path} is not a persistent volume. Mount Azure Files there before deployment."
        )
    if model_path.is_file() and model_path.stat().st_size > 500_000_000:
        logger.info("Qwen3 Embedding already cached at %s", model_path)
        return model_path

    model_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(model_path) + ".download.lock", timeout=900)
    with lock:
        if not model_path.is_file() or model_path.stat().st_size <= 500_000_000:
            repo_id = str(
                cfg(
                    "embeddings",
                    "local_runtime_repository",
                    default="Qwen/Qwen3-Embedding-0.6B-GGUF",
                )
            )
            filename = str(
                cfg(
                    "embeddings",
                    "local_model_filename",
                    default="Qwen3-Embedding-0.6B-Q8_0.gguf",
                )
            )
            logger.info("Downloading %s/%s into %s", repo_id, filename, model_path.parent)
            downloaded = Path(
                hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                    local_dir=model_path.parent,
                    token=env("HF_TOKEN"),
                )
            )
            if downloaded.resolve() != model_path.resolve():
                raise RuntimeError(
                    f"Qwen3 Embedding downloaded to unexpected path {downloaded}; expected {model_path}"
                )
    if not model_path.is_file() or model_path.stat().st_size <= 500_000_000:
        raise RuntimeError("Qwen3 Embedding model download is incomplete")
    logger.info("Qwen3 Embedding ready at %s", model_path)
    return model_path


if __name__ == "__main__":
    setup_logging()
    ensure_local_embedding_model()
