#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time

import httpx

from common import CheckFailed, config, require_env, require_response, run


def check() -> str:
    parser = argparse.ArgumentParser(description="Test the configured YouTube Data API key.")
    parser.add_argument("--query", default="Python developer interview questions")
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(config("youtube_qna", "timeout_seconds", default=60) or 60),
    )
    args = parser.parse_args()

    started = time.monotonic()
    response = httpx.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "key": require_env("YOUTUBE_API_KEY"),
            "part": "snippet",
            "type": "video",
            "maxResults": 1,
            "q": args.query,
        },
        timeout=args.timeout,
    )
    require_response(response, "YouTube search")
    items = response.json().get("items") or []
    if not items or not (items[0].get("id") or {}).get("videoId"):
        raise CheckFailed("YouTube API returned no video results")
    title = ((items[0].get("snippet") or {}).get("title") or "untitled")[:100]
    return f'YouTube returned "{title}" in {time.monotonic() - started:.2f}s'


if __name__ == "__main__":
    raise SystemExit(run(check))
