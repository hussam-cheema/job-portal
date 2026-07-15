from __future__ import annotations

import os
from typing import Any, Optional

from app.config import cfg, env, load_config
from app.logging_config import get_logger

logger = get_logger("jobportal.llm")

PROVIDER_ENV = {
    "grok": ("GROK_API_KEY", "GROK_BASE_URL", "https://api.x.ai/v1"),
    "openai": ("OPENAI_API_KEY", "OPENAI_BASE_URL", "https://api.openai.com/v1"),
    "deepseek": ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    "meta": ("META_API_KEY", "META_BASE_URL", "https://api.together.xyz/v1"),
    "glm": ("GLM_API_KEY", "GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
    "ollama": ("OLLAMA_API_KEY", "OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    "claude": ("CLAUDE_API_KEY", "CLAUDE_BASE_URL", "https://api.anthropic.com/v1"),
}


def _placeholder(key: Optional[str]) -> bool:
    if not key:
        return True
    low = key.lower()
    return any(p in low for p in ("your-", "changeme", "xxx", "todo", "replace", "sk-your"))


def _provider_enabled(name: str) -> bool:
    providers = (load_config().get("llm") or {}).get("providers") or {}
    conf = providers.get(name) or {}
    return bool(conf.get("enabled", False))


def _credentials(provider: str) -> dict[str, Optional[str]]:
    key_env, url_env, default_url = PROVIDER_ENV.get(provider, ("", "", None))
    api_key = env(key_env) if key_env else None
    base_url = env(url_env) or default_url
    if provider == "ollama":
        api_key = api_key or "ollama"
    return {"api_key": api_key, "base_url": base_url}


def list_usable_providers() -> list[str]:
    out = []
    for name in PROVIDER_ENV:
        if not _provider_enabled(name):
            continue
        creds = _credentials(name)
        if name == "ollama" or not _placeholder(creds["api_key"]):
            out.append(name)
    return out


def resolve_task_llm(task: str = "qna_extraction") -> dict[str, Any]:
    llm = load_config().get("llm") or {}
    tasks = llm.get("tasks") or {}
    task_cfg = tasks.get(task) or tasks.get("extraction") or {}
    preferred = (task_cfg.get("provider") or "deepseek").lower()
    fallbacks = [str(x).lower() for x in (task_cfg.get("fallback") or [])]
    order = [preferred] + [f for f in fallbacks if f != preferred]
    providers_cfg = llm.get("providers") or {}

    for name in order:
        if name not in PROVIDER_ENV:
            continue
        if not _provider_enabled(name) and name != preferred:
            continue
        creds = _credentials(name)
        if name != "ollama" and _placeholder(creds["api_key"]):
            continue
        if name == preferred and not _provider_enabled(name):
            # still try preferred if key present
            if name != "ollama" and _placeholder(creds["api_key"]):
                continue
        pconf = providers_cfg.get(name) or {}
        model = task_cfg.get("model") or pconf.get("model") or "gpt-4o-mini"
        return {
            "provider": name,
            "model": model,
            "api_key": creds["api_key"],
            "base_url": creds["base_url"],
            "temperature": float(llm.get("temperature", 0.1)),
            "max_tokens": int(llm.get("max_tokens", 4096)),
            "thinking": bool(task_cfg.get("thinking", False)),
            "response_format": task_cfg.get("response_format"),
            "empty_response_retries": max(
                0, int(task_cfg.get("empty_response_retries") or 0)
            ),
        }

    # last resort: ollama local
    return {
        "provider": "ollama",
        "model": ((providers_cfg.get("ollama") or {}).get("model") or "llama3.2"),
        "api_key": "ollama",
        "base_url": env("OLLAMA_BASE_URL") or "http://localhost:11434/v1",
        "temperature": 0.1,
        "max_tokens": 4096,
        "thinking": False,
        "response_format": None,
        "empty_response_retries": 0,
    }


def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    timeout_seconds: float = 30,
) -> str:
    """OpenAI-compatible chat completion across providers."""
    resolved = resolve_task_llm("qna_extraction")
    provider = resolved["provider"]
    temp = resolved["temperature"] if temperature is None else temperature
    logger.info(
        "chat_completion_request task=qna_extraction provider=%s model=%s",
        provider,
        resolved["model"],
    )

    try:
        if provider == "claude":
            return _claude_chat(messages, resolved, temp, timeout_seconds)

        import httpx

        url = f"{str(resolved['base_url']).rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {resolved['api_key'] or 'not-needed'}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": resolved["model"],
            "messages": messages,
            "temperature": temp,
            "max_tokens": resolved["max_tokens"],
        }
        if provider == "deepseek":
            payload["thinking"] = {
                "type": "enabled" if resolved.get("thinking") else "disabled"
            }
        if resolved.get("response_format") == "json_object":
            payload["response_format"] = {"type": "json_object"}

        retries = int(resolved.get("empty_response_retries") or 0)
        with httpx.Client(timeout=max(1.0, timeout_seconds)) as client:
            for attempt in range(retries + 1):
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                choice = (data.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                content = message.get("content")
                if content is not None and str(content).strip():
                    return content if isinstance(content, str) else str(content)
                logger.warning(
                    "empty_chat_completion provider=%s model=%s finish_reason=%s attempt=%s",
                    provider,
                    resolved["model"],
                    choice.get("finish_reason"),
                    attempt + 1,
                )
                if attempt < retries:
                    # DeepSeek documents that JSON mode can occasionally return
                    # empty content. Retry once without the response-format flag;
                    # the extraction prompt still explicitly requires JSON.
                    payload.pop("response_format", None)
                    payload["messages"] = [
                        *messages,
                        {
                            "role": "user",
                            "content": "Return the requested non-empty JSON object now.",
                        },
                    ]
        raise RuntimeError(
            f"{provider} returned an empty completion after {retries + 1} attempt(s)"
        )
    except Exception:
        logger.exception("chat_completion failed provider=%s", provider)
        raise


def _claude_chat(
    messages: list[dict[str, str]],
    resolved: dict[str, Any],
    temp: float,
    timeout_seconds: float,
) -> str:
    import httpx

    system = ""
    chat_msgs = []
    for m in messages:
        if m.get("role") == "system":
            system = m.get("content") or ""
        else:
            chat_msgs.append({"role": m.get("role", "user"), "content": m.get("content") or ""})

    url = f"{str(resolved['base_url']).rstrip('/')}/messages"
    headers = {
        "x-api-key": resolved["api_key"] or "",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": resolved["model"],
        "max_tokens": resolved["max_tokens"],
        "temperature": temp,
        "system": system,
        "messages": chat_msgs or [{"role": "user", "content": ""}],
    }
    with httpx.Client(timeout=max(1.0, timeout_seconds)) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    parts = data.get("content") or []
    texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
    return "\n".join(texts)
