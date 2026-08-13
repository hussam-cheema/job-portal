from __future__ import annotations

import json
import mimetypes
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from app.config import cfg, env
from app.logging_config import get_logger

logger = get_logger("jobportal.youtube")


class YouTubeProviderError(RuntimeError):
    """Raised when neither YouTube API nor yt-dlp can complete a request."""


def _yt_cfg() -> dict:
    return dict(cfg("youtube_qna") or {})


def _has_api_key() -> bool:
    key = (env("YOUTUBE_API_KEY") or "").strip()
    if not key:
        return False
    low = key.lower()
    return not any(p in low for p in ("your-", "changeme", "xxx", "todo", "replace"))


def _usable_secret(value: str | None) -> bool:
    clean = (value or "").strip()
    if not clean:
        return False
    low = clean.lower()
    return not any(p in low for p in ("your-", "changeme", "xxx", "todo", "replace"))


def search_youtube(
    query: str,
    max_results: int | None = None,
    *,
    timeout_seconds: float = 10,
    raise_on_failure: bool = False,
) -> list[dict[str, Any]]:
    conf = _yt_cfg()
    if not conf.get("enabled", True):
        return []
    max_results = max_results or int(conf.get("max_youtube_search_results") or 50)

    api_error: Exception | None = None
    if _has_api_key():
        try:
            videos = _search_api(query, max_results, timeout_seconds)
            logger.info("youtube_search_api query=%s count=%s", query, len(videos))
            return videos
        except Exception as exc:
            api_error = exc
            logger.exception("youtube_api_search_failed — fallback yt-dlp")

    try:
        return _search_ytdlp(query, max_results, timeout_seconds)
    except FileNotFoundError as exc:
        logger.warning("yt_dlp_not_installed")
        fallback_error: Exception = exc
    except Exception as exc:
        logger.exception("youtube_search_error")
        fallback_error = exc
    if raise_on_failure:
        detail = fallback_error or api_error or RuntimeError("YouTube search unavailable")
        raise YouTubeProviderError("YouTube search could not be completed") from detail
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
            "order": "date",
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
                "published_at": snippet.get("publishedAt") or "",
            }
        )
    return videos


def _search_ytdlp(query: str, max_results: int, timeout_seconds: float) -> list[dict[str, Any]]:
    cmd = [
        "yt-dlp",
        f"ytsearchdate{max_results}:{query}",
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
        raise RuntimeError((proc.stderr or "yt-dlp YouTube search failed")[:300])

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
                "published_at": (
                    item.get("upload_date")
                    or item.get("release_timestamp")
                    or item.get("timestamp")
                    or ""
                ),
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
        transcript = _transcript_ytdlp(
            video_id,
            timeout_seconds=float(_yt_cfg().get("source_timeout_seconds") or 60),
        )
        if transcript:
            return transcript
    except Exception as exc:
        logger.debug("transcript_ytdlp_failed video_id=%s error=%s", video_id, exc)

    # Many relevant job videos have neither authored nor auto-generated
    # captions. When an OpenAI key is already configured for embeddings, use
    # the same public video audio to create the missing transcript. DeepSeek is
    # still responsible for the subsequent Q&A extraction.
    conf = _yt_cfg()
    if conf.get("transcribe_audio_when_captions_missing", True):
        try:
            transcript = _transcript_openai_audio(
                video_id,
                timeout_seconds=float(
                    conf.get("audio_transcription_timeout_seconds") or 120
                ),
            )
            if transcript:
                return transcript
        except Exception as exc:
            logger.warning(
                "transcript_audio_fallback_failed video_id=%s error=%s",
                video_id,
                str(exc)[:200],
            )
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
            timeout=max(1.0, min(60.0, timeout_seconds)),
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


def _transcript_openai_audio(video_id: str, *, timeout_seconds: float) -> str | None:
    """Download a bounded public audio stream and transcribe it when captions are absent."""
    api_key = env("OPENAI_API_KEY")
    if not _usable_secret(api_key):
        return None
    conf = _yt_cfg()
    max_bytes = max(
        1_000_000,
        min(24_000_000, int(conf.get("max_transcription_audio_bytes") or 24_000_000)),
    )
    with tempfile.TemporaryDirectory(prefix="jobportal-youtube-audio-") as directory:
        output = str(Path(directory) / "audio.%(ext)s")
        proc = subprocess.run(
            [
                "yt-dlp",
                f"https://www.youtube.com/watch?v={video_id}",
                "--no-playlist",
                "--format",
                "bestaudio[filesize<24M]/bestaudio[filesize_approx<24M]/bestaudio",
                "--max-filesize",
                str(max_bytes),
                "--output",
                output,
                "--quiet",
                "--no-warnings",
                "--no-progress",
            ],
            capture_output=True,
            text=True,
            timeout=max(1.0, min(60.0, timeout_seconds)),
            check=False,
        )
        audio_files = sorted(
            path
            for path in Path(directory).glob("audio.*")
            if path.is_file() and path.suffix != ".part"
        )
        if proc.returncode != 0 or not audio_files:
            return None
        audio_path = audio_files[0]
        if audio_path.stat().st_size > max_bytes:
            logger.warning(
                "youtube_audio_too_large video_id=%s bytes=%s",
                video_id,
                audio_path.stat().st_size,
            )
            return None

        base_url = (
            env("OPENAI_TRANSCRIPTION_BASE_URL")
            or env("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        model = str(
            env("OPENAI_TRANSCRIPTION_MODEL")
            or conf.get("audio_transcription_model")
            or "gpt-4o-mini-transcribe"
        )
        mime_type = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
        with audio_path.open("rb") as audio:
            response = httpx.post(
                f"{base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": model, "response_format": "json"},
                files={"file": (audio_path.name, audio, mime_type)},
                timeout=max(1.0, timeout_seconds),
            )
        response.raise_for_status()
        payload = response.json()
        transcript = str(payload.get("text") or "").strip()
        if transcript:
            logger.info(
                "youtube_audio_transcribed video_id=%s model=%s chars=%s",
                video_id,
                model,
                len(transcript),
            )
        return transcript or None


def get_top_comments(
    video_id: str,
    max_comments: int | None = None,
    *,
    timeout_seconds: float = 10,
    raise_on_failure: bool = False,
) -> list[str]:
    conf = _yt_cfg()
    if not conf.get("extract_comments", True):
        return []
    max_comments = max_comments or int(conf.get("max_comments") or 50)

    api_error: Exception | None = None
    if _has_api_key():
        try:
            return _comments_api(video_id, max_comments, timeout_seconds)
        except Exception as exc:
            api_error = exc
            logger.exception("youtube_api_comments_failed — fallback yt-dlp")

    try:
        return _comments_ytdlp(video_id, max_comments, timeout_seconds)
    except FileNotFoundError as exc:
        fallback_error: Exception = exc
    except Exception as exc:
        logger.debug("comments_failed video_id=%s error=%s", video_id, exc)
        fallback_error = exc
    if raise_on_failure:
        detail = fallback_error or api_error or RuntimeError("YouTube comments unavailable")
        raise YouTubeProviderError("YouTube comments could not be completed") from detail
    return []


def _comments_api(video_id: str, max_comments: int, timeout_seconds: float) -> list[str]:
    comments: list[str] = []
    page_token: str | None = None
    limit = max(1, min(int(max_comments), 500))
    while len(comments) < limit:
        params: dict[str, Any] = {
            "part": "snippet,replies",
            "videoId": video_id,
            "maxResults": min(limit - len(comments), 100),
            "textFormat": "plainText",
            "order": "time",
            "key": env("YOUTUBE_API_KEY"),
        }
        if page_token:
            params["pageToken"] = page_token
        response = httpx.get(
            "https://www.googleapis.com/youtube/v3/commentThreads",
            params=params,
            timeout=max(1.0, timeout_seconds),
        )
        response.raise_for_status()
        payload = response.json()
        for item in payload.get("items", []):
            snippet = item.get("snippet") or {}
            top_level = snippet.get("topLevelComment") or {}
            top = top_level.get("snippet") or {}
            text = str(top.get("textDisplay") or "").strip()
            if not text:
                continue
            embedded = list((item.get("replies") or {}).get("comments") or [])
            replies = [
                reply
                for row in embedded
                if (reply := str((row.get("snippet") or {}).get("textDisplay") or "").strip())
            ]
            parent_id = str(top_level.get("id") or "")
            total_replies = int(snippet.get("totalReplyCount") or len(replies))
            if parent_id and total_replies > len(replies):
                try:
                    replies = _comment_replies_api(
                        parent_id,
                        timeout_seconds=timeout_seconds,
                    ) or replies
                except Exception as exc:
                    logger.debug("youtube_reply_fetch_failed parent_id=%s error=%s", parent_id, exc)
            comments.append(_format_comment_thread(text, replies))
            if len(comments) >= limit:
                break
        page_token = str(payload.get("nextPageToken") or "") or None
        if not page_token or not payload.get("items"):
            break
    return comments


def _comment_replies_api(
    parent_id: str,
    *,
    timeout_seconds: float,
) -> list[str]:
    replies: list[str] = []
    page_token: str | None = None
    while True:
        params: dict[str, Any] = {
            "part": "snippet",
            "parentId": parent_id,
            "maxResults": 100,
            "textFormat": "plainText",
            "key": env("YOUTUBE_API_KEY"),
        }
        if page_token:
            params["pageToken"] = page_token
        response = httpx.get(
            "https://www.googleapis.com/youtube/v3/comments",
            params=params,
            timeout=max(1.0, timeout_seconds),
        )
        response.raise_for_status()
        payload = response.json()
        replies.extend(
            text
            for item in payload.get("items", [])
            if (text := str((item.get("snippet") or {}).get("textDisplay") or "").strip())
        )
        page_token = str(payload.get("nextPageToken") or "") or None
        if not page_token:
            return replies


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
        for comment_id, text in roots[:max_comments]:
            standalone.append(
                _format_comment_thread(text, by_parent.get(comment_id, []))
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
