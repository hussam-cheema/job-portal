#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time

import httpx

from common import CheckFailed, config, env, require_env, require_response, run


def check() -> str:
    parser = argparse.ArgumentParser(description="Test the configured DeepSeek chat API.")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    api_key = require_env("DEEPSEEK_API_KEY")
    base_url = (env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1") or "").rstrip("/")
    model = str(
        config("llm", "tasks", "qna_extraction", "api_model", default=None)
        or config("llm", "tasks", "qna_extraction", "model", default=None)
        or config("llm", "providers", "deepseek", "api_model", default=None)
        or config("llm", "providers", "deepseek", "model", default="deepseek-chat")
    )
    started = time.monotonic()
    with httpx.Client(timeout=args.timeout) as client:
        response = client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly: API_OK"}],
                "temperature": 0,
                "max_tokens": 128,
            },
        )
    require_response(response, "DeepSeek chat completion")
    choices = response.json().get("choices") or []
    message = choices[0].get("message") if choices else {}
    content = (message or {}).get("content") or (message or {}).get("reasoning_content") or ""
    if not content.strip():
        finish_reason = choices[0].get("finish_reason") if choices else "missing choice"
        raise CheckFailed(f"DeepSeek returned no assistant content (finish_reason={finish_reason})")
    elapsed = time.monotonic() - started
    return f"DeepSeek responded with model {model} in {elapsed:.2f}s"


if __name__ == "__main__":
    raise SystemExit(run(check))
