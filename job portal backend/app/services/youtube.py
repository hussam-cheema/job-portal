from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from app.config import cfg, env
from app.logging_config import get_logger

logger = get_logger("jobportal.youtube")


def _yt_cfg() -> dict:
    return dict(cfg("youtube_qna") or {})


def _has_api_key() -> bool:
    key = (env("YOUTUBE_API_KEY") or "").strip()
    if not key:
        return False
    low = key.lower()
    return not any(p in low for p in ("your-", "changeme", "xxx", "todo", "replace"))


def search_youtube(
    query: str,
    max_results: int | None = None,
    *,
    timeout_seconds: float = 10,
) -> list[dict[str, Any]]:
    conf = _yt_cfg()
    if not conf.get("enabled", True):
        return []
    max_results = max_results or int(conf.get("max_youtube_search_results") or 50)

    if _has_api_key():
        try:
            videos = _search_api(query, max_results, timeout_seconds)
            if videos:
                logger.info("youtube_search_api query=%s count=%s", query, len(videos))
                return videos
        except Exception:
            logger.exception("youtube_api_search_failed — fallback yt-dlp")

    try:
        return _search_ytdlp(query, max_results, timeout_seconds)
    except FileNotFoundError:
        logger.warning("yt_dlp_not_installed")
        return []
    except Exception:
        logger.exception("youtube_search_error")
        return []


def _search_api(query: str, max_results: int, timeout_seconds: float) -> list[dict[str, Any]]:
    # The YouTube Search API accepts at most 50 results in one request.
    max_results = max(1, min(int(max_results), 50))
    response = httpx.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": max_results,
            "relevanceLanguage": "en",
            "key": env("YOUTUBE_API_KEY"),
        },
        timeout=max(1.0, timeout_seconds),
    )
    response.raise_for_status()
    payload = response.json()
    videos: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        video_id = (item.get("id") or {}).get("videoId")
        if not video_id:
            continue
        snippet = item.get("snippet") or {}
        videos.append(
            {
                "video_id": video_id,
                "title": snippet.get("title") or f"Video {video_id}",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "description": snippet.get("description") or "",
                "channel": snippet.get("channelTitle") or "",
            }
        )
    return videos


def _search_ytdlp(query: str, max_results: int, timeout_seconds: float) -> list[dict[str, Any]]:
    cmd = [
        "yt-dlp",
        f"ytsearch{max_results}:{query}",
        "--dump-json",
        "--flat-playlist",
        "--no-download",
        "--quiet",
        "--no-warnings",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=max(1.0, timeout_seconds),
        check=False,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        logger.warning("yt_dlp_search_failed stderr=%s", (proc.stderr or "")[:300])
        return []

    videos: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        video_id = item.get("id") or item.get("url")
        if not video_id:
            continue
        if "http" in str(video_id):
            m = re.search(r"(?:v=|youtu\.be/)([\w-]{6,})", str(video_id))
            video_id = m.group(1) if m else None
        if not video_id:
            continue
        videos.append(
            {
                "video_id": video_id,
                "title": item.get("title") or f"Video {video_id}",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "description": item.get("description") or item.get("title") or "",
                "channel": item.get("channel") or item.get("uploader") or "",
            }
        )
    return videos[:max_results]


def get_transcript(video_id: str) -> str | None:
    if not _yt_cfg().get("extract_transcripts", True):
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        try:
            api = YouTubeTranscriptApi()
            chunks = api.fetch(video_id)
            texts = []
            for c in chunks:
                if isinstance(c, dict):
                    texts.append(c.get("text", ""))
                else:
                    texts.append(getattr(c, "text", str(c)))
            transcript = " ".join(texts).strip()
            if transcript:
                return transcript
        except Exception:
            chunks = YouTubeTranscriptApi.get_transcript(video_id)
            transcript = " ".join(c.get("text", "") for c in chunks).strip()
            if transcript:
                return transcript
    except Exception as exc:
        logger.debug("transcript_api_failed video_id=%s error=%s", video_id, exc)

    # YouTube can deny the transcript endpoint while still exposing authored or
    # auto-generated subtitle tracks to yt-dlp. This independent fallback keeps
    # those English/Urdu captions available without downloading the video.
    try:
        return _transcript_ytdlp(
            video_id,
            timeout_seconds=float(_yt_cfg().get("source_timeout_seconds") or 60),
        )
    except Exception as exc:
        logger.debug("transcript_ytdlp_failed video_id=%s error=%s", video_id, exc)
        return None


def _transcript_ytdlp(video_id: str, *, timeout_seconds: float) -> str | None:
    with tempfile.TemporaryDirectory(prefix="jobportal-youtube-") as directory:
        output = str(Path(directory) / "%(id)s.%(ext)s")
        proc = subprocess.run(
            [
                "yt-dlp",
                f"https://www.youtube.com/watch?v={video_id}",
                "--skip-download",
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                "en.*,ur.*,en,ur",
                "--sub-format",
                "json3",
                "--output",
                output,
                "--quiet",
                "--no-warnings",
            ],
            capture_output=True,
            text=True,
            timeout=max(1.0, timeout_seconds),
            check=False,
        )
        subtitle_files = sorted(Path(directory).glob(f"{video_id}*.json3"))
        if proc.returncode != 0 and not subtitle_files:
            return None
        for path in subtitle_files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            parts: list[str] = []
            for event in data.get("events") or []:
                text = "".join(
                    str(segment.get("utf8") or "")
                    for segment in event.get("segs") or []
                    if isinstance(segment, dict)
                ).replace("\n", " ").strip()
                if text and text != "[Music]":
                    parts.append(text)
            transcript = " ".join(parts).strip()
            if transcript:
                return transcript
    return None


def get_top_comments(
    video_id: str,
    max_comments: int | None = None,
    *,
    timeout_seconds: float = 10,
) -> list[str]:
    conf = _yt_cfg()
    if not conf.get("extract_comments", True):
        return []
    max_comments = max_comments or int(conf.get("max_comments") or 50)

    if _has_api_key():
        try:
            comments = _comments_api(video_id, max_comments, timeout_seconds)
            if comments:
                return comments
        except Exception:
            logger.exception("youtube_api_comments_failed — fallback yt-dlp")

    try:
        return _comments_ytdlp(video_id, max_comments, timeout_seconds)
    except FileNotFoundError:
        return []
    except Exception as exc:
        logger.debug("comments_failed video_id=%s error=%s", video_id, exc)
        return []


def _comments_api(video_id: str, max_comments: int, timeout_seconds: float) -> list[str]:
    conf = _yt_cfg()
    max_reply_threads = max(0, int(conf.get("max_comment_reply_threads") or 12))
    max_replies = max(1, int(conf.get("max_replies_per_thread") or 10))
    response = httpx.get(
        "https://www.googleapis.com/youtube/v3/commentThreads",
        params={
            "part": "snippet,replies",
            "videoId": video_id,
            "maxResults": min(max_comments, 100),
            "textFormat": "plainText",
            "order": "relevance",
            "key": env("YOUTUBE_API_KEY"),
        },
        timeout=max(1.0, timeout_seconds),
    )
    response.raise_for_status()
    payload = response.json()
    comments: list[str] = []
    reply_fetches = 0
    for item in payload.get("items", [])[:max_comments]:
        snippet = item.get("snippet") or {}
        top_level = snippet.get("topLevelComment") or {}
        top = top_level.get("snippet") or {}
        text = (top.get("textDisplay") or "").strip()
        if not text:
            continue
        reply_rows = list((item.get("replies") or {}).get("comments") or [])
        replies = [
            str((row.get("snippet") or {}).get("textDisplay") or "").strip()
            for row in reply_rows
        ]
        replies = [reply for reply in replies if reply]
        total_replies = int(snippet.get("totalReplyCount") or len(replies))
        parent_id = str(top_level.get("id") or "")
        if (
            parent_id
            and total_replies > len(replies)
            and reply_fetches < max_reply_threads
        ):
            reply_fetches += 1
            try:
                replies = _comment_replies_api(
                    parent_id,
                    max_replies=max_replies,
                    timeout_seconds=timeout_seconds,
                ) or replies
            except Exception as exc:
                logger.debug("youtube_reply_fetch_failed parent_id=%s error=%s", parent_id, exc)
        comments.append(_format_comment_thread(text, replies[:max_replies]))
    return comments


def _comment_replies_api(
    parent_id: str,
    *,
    max_replies: int,
    timeout_seconds: float,
) -> list[str]:
    response = httpx.get(
        "https://www.googleapis.com/youtube/v3/comments",
        params={
            "part": "snippet",
            "parentId": parent_id,
            "maxResults": min(max_replies, 100),
            "textFormat": "plainText",
            "key": env("YOUTUBE_API_KEY"),
        },
        timeout=max(1.0, timeout_seconds),
    )
    response.raise_for_status()
    return [
        text
        for item in response.json().get("items", [])
        if (text := str((item.get("snippet") or {}).get("textDisplay") or "").strip())
    ]


def _format_comment_thread(top_level: str, replies: list[str]) -> str:
    lines = [f"TOP-LEVEL COMMENT: {top_level.strip()}"]
    lines.extend(
        f"REPLY {index}: {reply.strip()}"
        for index, reply in enumerate(replies, start=1)
        if reply.strip()
    )
    return "\n".join(lines)


def _comments_ytdlp(video_id: str, max_comments: int, timeout_seconds: float) -> list[str]:
    cmd = [
        "yt-dlp",
        f"https://www.youtube.com/watch?v={video_id}",
        "--skip-download",
        "--write-comments",
        "--no-warnings",
        "-J",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=max(1.0, timeout_seconds),
        check=False,
    )
    if not proc.stdout.strip():
        return []
    data = json.loads(proc.stdout)
    rows = [row for row in data.get("comments") or [] if isinstance(row, dict)]
    by_parent: dict[str, list[str]] = {}
    roots: list[tuple[str, str]] = []
    standalone: list[str] = []
    for index, row in enumerate(rows):
        text = str(row.get("text") or row.get("comment") or "").strip()
        if not text:
            continue
        comment_id = str(row.get("id") or f"comment-{index}")
        parent = str(row.get("parent") or "").strip()
        if parent and parent not in {"root", "None"}:
            by_parent.setdefault(parent, []).append(text)
        else:
            roots.append((comment_id, text))
    if roots:
        max_replies = max(1, int(_yt_cfg().get("max_replies_per_thread") or 10))
        for comment_id, text in roots[:max_comments]:
            standalone.append(
                _format_comment_thread(text, by_parent.get(comment_id, [])[:max_replies])
            )
        return standalone

    # Older yt-dlp payloads may not expose ids/parents. Preserve those comments
    # individually rather than discarding them.
    for row in (data.get("comments") or [])[:max_comments]:
        text = str(
            (row.get("text") or row.get("comment") or "")
            if isinstance(row, dict)
            else row
        ).strip()
        if text:
            standalone.append(text)
    return standalone
