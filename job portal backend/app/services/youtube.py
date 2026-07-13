from __future__ import annotations

import json
import re
import subprocess
from typing import Any

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


def search_youtube(query: str, max_results: int | None = None) -> list[dict[str, Any]]:
    conf = _yt_cfg()
    if not conf.get("enabled", True):
        return []
    max_results = max_results or int(conf.get("max_youtube_videos") or 5)

    if _has_api_key():
        try:
            videos = _search_api(query, max_results)
            if videos:
                logger.info("youtube_search_api query=%s count=%s", query, len(videos))
                return videos
        except Exception:
            logger.exception("youtube_api_search_failed — fallback yt-dlp")

    try:
        return _search_ytdlp(query, max_results)
    except FileNotFoundError:
        logger.warning("yt_dlp_not_installed")
        return []
    except Exception:
        logger.exception("youtube_search_error")
        return []


def _search_api(query: str, max_results: int) -> list[dict[str, Any]]:
    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", developerKey=env("YOUTUBE_API_KEY"))
    response = (
        youtube.search()
        .list(q=query, part="snippet", type="video", maxResults=max_results, relevanceLanguage="en")
        .execute()
    )
    videos: list[dict[str, Any]] = []
    for item in response.get("items", []):
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


def _search_ytdlp(query: str, max_results: int) -> list[dict[str, Any]]:
    cmd = [
        "yt-dlp",
        f"ytsearch{max_results}:{query}",
        "--dump-json",
        "--flat-playlist",
        "--no-download",
        "--quiet",
        "--no-warnings",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
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
            return " ".join(texts).strip() or None
        except Exception:
            chunks = YouTubeTranscriptApi.get_transcript(video_id)
            return " ".join(c.get("text", "") for c in chunks).strip() or None
    except Exception as exc:
        logger.debug("transcript_failed video_id=%s error=%s", video_id, exc)
        return None


def get_top_comments(video_id: str, max_comments: int | None = None) -> list[str]:
    conf = _yt_cfg()
    if not conf.get("extract_comments", True):
        return []
    max_comments = max_comments or int(conf.get("max_comments") or 50)

    if _has_api_key():
        try:
            comments = _comments_api(video_id, max_comments)
            if comments:
                return comments
        except Exception:
            logger.exception("youtube_api_comments_failed — fallback yt-dlp")

    try:
        return _comments_ytdlp(video_id, max_comments)
    except FileNotFoundError:
        return []
    except Exception as exc:
        logger.debug("comments_failed video_id=%s error=%s", video_id, exc)
        return []


def _comments_api(video_id: str, max_comments: int) -> list[str]:
    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", developerKey=env("YOUTUBE_API_KEY"))
    response = (
        youtube.commentThreads()
        .list(
            part="snippet",
            videoId=video_id,
            maxResults=min(max_comments, 100),
            textFormat="plainText",
            order="relevance",
        )
        .execute()
    )
    comments: list[str] = []
    for item in response.get("items", []):
        top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        text = (top.get("textDisplay") or "").strip()
        if text:
            comments.append(text)
    return comments


def _comments_ytdlp(video_id: str, max_comments: int) -> list[str]:
    cmd = [
        "yt-dlp",
        f"https://www.youtube.com/watch?v={video_id}",
        "--skip-download",
        "--write-comments",
        "--no-warnings",
        "-J",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    if not proc.stdout.strip():
        return []
    data = json.loads(proc.stdout)
    out: list[str] = []
    for c in data.get("comments") or []:
        if isinstance(c, dict):
            text = c.get("text") or c.get("comment") or ""
        else:
            text = str(c)
        text = text.strip()
        if text:
            out.append(text)
        if len(out) >= max_comments:
            break
    return out
