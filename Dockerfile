# syntax=docker/dockerfile:1

# Unkey builds from the repository root because its configured build root cannot
# contain spaces. This keeps the Python service in its existing monorepo path.
FROM python:3.12-slim AS wheels

ENV CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_OPENMP=OFF -DGGML_BLAS=OFF"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

COPY ["job portal backend/requirements.txt", "."]
RUN pip install --upgrade pip && pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LOG_LEVEL=INFO \
    SEED_ON_STARTUP=false \
    PORT=8000 \
    WEB_CONCURRENCY=1 \
    QWEN3_EMBEDDING_MODEL_PATH=/models/Qwen3-Embedding-0.6B-Q8_0.gguf \
    QWEN3_EMBEDDING_MODEL_MOUNT_PATH=/models \
    QWEN3_EMBEDDING_REQUIRE_PERSISTENT_STORAGE=false \
    QWEN3_EMBEDDING_CACHE_BACKGROUND=true \
    QWEN3_EMBEDDING_THREADS=1 \
    HF_HUB_DISABLE_TELEMETRY=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    libreoffice-writer \
    fontconfig \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY --from=wheels /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/* && rm -rf /wheels

COPY ["job portal backend/app", "./app"]
COPY ["job portal backend/migration", "./migration"]
COPY ["job portal backend/config.yaml", "./config.yaml"]

# Keep the local embedding fallback inside the immutable image. Unkey instances
# are ephemeral and only provide a small writable scratch filesystem.
RUN python -m app.services.model_cache

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/ready" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}"]
