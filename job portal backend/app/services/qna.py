from __future__ import annotations

import json
import re
import time
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import cfg
from app.logging_config import get_logger
from app.models import JobQnA
from app.services.embeddings import (
    answer_matches_question,
    rank_by_similarity,
)
from app.services.llm import chat_completion
from app.services.youtube import get_top_comments, get_transcript, search_youtube

logger = get_logger("jobportal.qna")

SYSTEM = """You extract COMPLETE interview Question-and-Answer pairs for job seekers in Pakistan
from YouTube video transcripts and comments.

Return ONLY valid JSON:
{
  "qna": [
    {
      "question": "...",
      "answer": "...",
      "source": "transcript|comment|mixed"
    }
  ]
}

STRICT RULES:
1. Only include pairs where BOTH a clear question AND a real answer exist.
2. If a question has no answer in the transcript or comments, SKIP it entirely.
3. An answer may appear in a different comment than the question, or in the video transcript.
4. Prefer concrete, useful interview Q&A (not generic chit-chat).
5. Do NOT invent answers. Do NOT use placeholders like "See video" or "N/A".
6. Max 20 QnA pairs total.
7. If nothing useful, return {"qna": []}.
"""


def _safe_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"qna": []}


def extract_qna_from_video(
    *,
    title: str,
    job_title: str,
    transcript: str | None,
    comments: list[str],
) -> list[dict[str, str]]:
    if not (transcript or comments):
        return []
    payload = (
        f"Job post title: {job_title}\n"
        f"Video title: {title}\n\n"
        f"TRANSCRIPT:\n{(transcript or '')[:12000]}\n\n"
        f"COMMENTS (may contain Q in one comment and A in another):\n"
        + "\n---\n".join(comments[:50])
    )
    try:
        content = chat_completion(
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": payload},
            ],
            temperature=0.1,
        )
        data = _safe_json(content)
        items: list[dict[str, str]] = []
        for row in data.get("qna") or []:
            q = (row.get("question") or "").strip()
            a = (row.get("answer") or "").strip()
            if not q or not a:
                continue
            if not answer_matches_question(q, a):
                continue
            items.append(
                {
                    "question": q,
                    "answer": a,
                    "source": (row.get("source") or "mixed"),
                }
            )
        return items
    except Exception:
        logger.exception("qna_llm_failed")
        return []


def fetch_qna_for_job_title(
    db: Session,
    *,
    job_id: str,
    job_title: str,
    replace_existing: bool = True,
) -> dict[str, Any]:
    """
    YouTube Data API search + transcripts + comments → LLM extracts complete Q&A pairs.
    Videos ranked by embedding similarity to job title. Max 20 pairs. Timeout configurable.
    """
    conf = cfg("youtube_qna") or {}
    max_qna = int(conf.get("max_qna") or 20)
    max_videos = int(conf.get("max_youtube_videos") or 5)
    timeout = float(conf.get("timeout_seconds") or 60)
    min_sim = float(conf.get("min_title_similarity") or 0.95)
    started = time.time()
    error: str | None = None
    search_succeeded = False
    collected: list[dict[str, Any]] = []
    videos_scanned = 0
    seen_q: set[str] = set()

    try:
        query = f"{job_title} interview questions answers Pakistan".strip()
        # Fetch more than max_videos then rank by embedding similarity
        raw_videos = search_youtube(query, max_results=max(max_videos * 2, max_videos))
        ranked = rank_by_similarity(
            job_title,
            raw_videos,
            key="title",
            score_key="title_similarity",
        )
        videos = [
            video
            for video in ranked
            if float(video.get("title_similarity") or 0) >= min_sim
        ][:max_videos]
        search_succeeded = True
        logger.info(
            "qna_title_filter job_id=%s threshold=%.2f candidates=%s matched=%s",
            job_id,
            min_sim,
            len(raw_videos),
            len(videos),
        )

        for video in videos:
            if time.time() - started >= timeout:
                logger.info("qna_timeout job_id=%s after %.1fs", job_id, time.time() - started)
                break
            if len(collected) >= max_qna:
                break
            video_id = video.get("video_id")
            if not video_id:
                continue
            videos_scanned += 1
            try:
                transcript = get_transcript(video_id)
                comments = get_top_comments(video_id)
                pairs = extract_qna_from_video(
                    title=video.get("title") or job_title,
                    job_title=job_title,
                    transcript=transcript,
                    comments=comments,
                )
                for p in pairs:
                    if time.time() - started >= timeout:
                        break
                    qkey = p["question"].strip().lower()
                    if qkey in seen_q:
                        continue
                    # re-check answer quality
                    if not answer_matches_question(p["question"], p["answer"]):
                        continue
                    seen_q.add(qkey)
                    collected.append(
                        {
                            "question": p["question"],
                            "answer": p["answer"],
                            "source": p.get("source"),
                            "youtube_url": video.get("url"),
                            "youtube_title": video.get("title"),
                        }
                    )
                    if len(collected) >= max_qna:
                        break
            except Exception as exc:
                logger.exception("qna video failed video_id=%s", video_id)
                error = str(exc)
    except Exception as exc:
        logger.exception("fetch_qna_for_job_title failed job_id=%s", job_id)
        error = str(exc)

    collected = collected[:max_qna]
    saved: list[JobQnA] = []
    try:
        if not search_succeeded:
            raise RuntimeError(error or "YouTube search did not complete")
        if replace_existing:
            db.query(JobQnA).filter(JobQnA.job_id == job_id).delete(synchronize_session=False)
        for item in collected:
            row = JobQnA(
                id=str(uuid4()),
                job_id=job_id,
                question=item["question"],
                answer=item["answer"],
                source=item.get("source"),
                youtube_url=item.get("youtube_url"),
                youtube_title=item.get("youtube_title"),
            )
            db.add(row)
            saved.append(row)
        # Delete and insert are committed together, so a failed refresh keeps the old set.
        db.commit()
        for row in saved:
            db.refresh(row)
    except Exception as exc:
        db.rollback()
        logger.exception("qna persist failed job_id=%s", job_id)
        error = str(exc)
        saved = []

    elapsed = time.time() - started
    return {
        "items": saved,
        "count": len(saved),
        "elapsed_seconds": round(elapsed, 2),
        "error": error,
        "videos_scanned": videos_scanned,
    }
