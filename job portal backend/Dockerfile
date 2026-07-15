# syntax=docker/dockerfile:1
FROM python:3.12-slim AS wheels

ENV CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_OPENMP=OFF -DGGML_BLAS=OFF"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
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
    EMBEDDINGGEMMA_MODEL_PATH=/models/embeddinggemma-300M-qat-Q4_0.gguf \
    EMBEDDINGGEMMA_MODEL_MOUNT_PATH=/models \
    EMBEDDINGGEMMA_THREADS=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=wheels /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/* && rm -rf /wheels

COPY app ./app
COPY config.yaml ./config.yaml
COPY .env.example ./.env.example

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/health" || exit 1

CMD ["sh", "-c", "python -m app.services.model_cache && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}"]
