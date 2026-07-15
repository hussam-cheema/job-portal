from __future__ import annotations

import json
import re
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
    wait,
)
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import cfg
from app.logging_config import get_logger
from app.models import JobQnA
from app.services.embeddings import rank_by_similarity
from app.services.llm import chat_completion
from app.services.youtube import get_top_comments, get_transcript, search_youtube

logger = get_logger("jobportal.qna")

SYSTEM = """You extract useful, source-grounded Question-and-Answer pairs for job seekers in
Pakistan from the supplied YouTube video transcripts and comments.

Return ONLY valid JSON:
{
  "qna": [
    {
      "question": "...",
      "answer": "...",
      "source": "transcript|comment|mixed",
      "video_index": 1
    }
  ]
}

GROUNDING RULES:
1. Every answer must be directly supported by at least one supplied transcript or comment.
2. A question may be explicit in the source, or you may turn a useful factual statement from
   the source into a natural question. Never add facts that are absent from the source.
3. A question and its answer may come from different comments, or from a transcript and a
   comment. They may also be supported by different supplied videos.
4. Prefer concrete job duties, eligibility, test syllabus, application process, preparation,
   interview questions, and factual answers relevant to the job title.
5. Ignore greetings, promotions, requests for likes/subscriptions, and unrelated discussion.
6. Do not use placeholders such as "See video", "N/A", or "contact us" as answers.
7. Set video_index to the source video that best supports the answer.
8. Return at least one pair whenever the supplied material contains any useful job-relevant
   factual statement. Return {"qna": []} only when no grounded job-relevant fact exists.
9. Return no more than the requested maximum number of pairs.
"""


def _safe_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    # Do not use a non-greedy ``{.*?}`` match here: it truncates nested Q&A JSON
    # at the first item and silently turns a valid model response into an empty set.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        decoded = json.loads(text)
        return decoded if isinstance(decoded, dict) else {"qna": decoded}
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for match in re.finditer(r"[\{\[]", text):
            try:
                decoded, _ = decoder.raw_decode(text[match.start() :])
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(decoded, dict):
                return decoded
            if isinstance(decoded, list):
                return {"qna": decoded}
        return {"qna": []}


def _source_payload(source: dict[str, Any], max_chars: int) -> str:
    transcript = str(source.get("transcript") or "").strip()
    comments = [str(value).strip() for value in source.get("comments") or [] if str(value).strip()]
    transcript_budget = int(max_chars * 0.7)
    transcript = transcript[:transcript_budget]
    remaining = max(0, max_chars - len(transcript))
    comment_lines: list[str] = []
    used = 0
    for index, comment in enumerate(comments, start=1):
        line = f"[{index}] {comment[:600]}"
        if used + len(line) + 1 > remaining:
            break
        comment_lines.append(line)
        used += len(line) + 1
    return (
        f"VIDEO INDEX: {source['video_index']}\n"
        f"VIDEO TITLE: {source.get('title') or ''}\n"
        f"TRANSCRIPT:\n{transcript or '[unavailable]'}\n"
        f"COMMENTS:\n{chr(10).join(comment_lines) or '[unavailable]'}"
    )


def extract_qna_from_sources(
    *,
    job_title: str,
    sources: list[dict[str, Any]],
    max_qna: int,
    max_source_chars_per_video: int,
    timeout_seconds: float = 60,
) -> list[dict[str, Any]]:
    usable = [source for source in sources if source.get("transcript") or source.get("comments")]
    if not usable:
        return []
    payload = (
        f"Job post title: {job_title}\n"
        f"Maximum Q&A pairs: {max_qna}\n\n"
        + "\n\n===== NEXT VIDEO =====\n\n".join(
            _source_payload(source, max_source_chars_per_video) for source in usable
        )
    )
    content = chat_completion(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": payload},
        ],
        temperature=0.1,
        timeout_seconds=timeout_seconds,
    )
    data = _safe_json(content)
    valid_indexes = {int(source["video_index"]) for source in usable}
    default_index = int(usable[0]["video_index"])
    items: list[dict[str, Any]] = []
    for row in data.get("qna") or []:
        if not isinstance(row, dict):
            continue
        question = str(row.get("question") or "").strip()
        answer = str(row.get("answer") or "").strip()
        if len(question) < 5 or len(answer) < 8:
            continue
        if answer.lower() in {"see video", "see video.", "n/a", "none", "unknown"}:
            continue
        try:
            video_index = int(row.get("video_index") or default_index)
        except (TypeError, ValueError):
            video_index = default_index
        if video_index not in valid_indexes:
            video_index = default_index
        items.append(
            {
                "question": question,
                "answer": answer,
                "source": str(row.get("source") or "mixed"),
                "video_index": video_index,
            }
        )
        if len(items) >= max_qna:
            break
    return items


def extract_qna_from_video(
    *,
    title: str,
    job_title: str,
    transcript: str | None,
    comments: list[str],
    timeout_seconds: float = 20,
) -> list[dict[str, str]]:
    """Backward-compatible single-video wrapper used by focused tests/tools."""
    rows = extract_qna_from_sources(
        job_title=job_title,
        sources=[
            {
                "video_index": 1,
                "title": title,
                "transcript": transcript,
                "comments": comments,
            }
        ],
        max_qna=20,
        max_source_chars_per_video=16000,
        timeout_seconds=timeout_seconds,
    )
    return [
        {"question": row["question"], "answer": row["answer"], "source": row["source"]}
        for row in rows
    ]


def _call_with_timeout(function, timeout_seconds: float):
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qna-external")
    future = executor.submit(function)
    try:
        return future.result(timeout=max(1.0, timeout_seconds))
    except FutureTimeoutError as exc:
        future.cancel()
        raise TimeoutError("external Q&A source timed out") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _collect_video_source(
    video: dict[str, Any],
    *,
    video_index: int,
    max_comments: int,
    source_timeout_seconds: float,
) -> dict[str, Any]:
    transcript: str | None = None
    comments: list[str] = []
    video_id = str(video.get("video_id") or "")
    try:
        transcript = _call_with_timeout(
            lambda: get_transcript(video_id), source_timeout_seconds
        )
    except Exception as exc:
        logger.warning(
            "qna_transcript_unavailable video_id=%s error=%s",
            video_id,
            str(exc)[:200],
        )
    try:
        comments = get_top_comments(
            video_id,
            max_comments=max_comments,
            timeout_seconds=source_timeout_seconds,
        )
    except Exception as exc:
        logger.warning(
            "qna_comments_unavailable video_id=%s error=%s",
            video_id,
            str(exc)[:200],
        )
    return {
        **video,
        "video_index": video_index,
        "transcript": transcript,
        "comments": comments,
    }


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
    max_search_results = int(conf.get("max_youtube_search_results") or 50)
    max_comments = int(conf.get("max_comments") or 50)
    timeout = float(conf.get("timeout_seconds") or 60)
    ai_timeout = float(
        conf.get("ai_timeout_seconds")
        or conf.get("per_video_ai_timeout_seconds")
        or 60
    )
    source_timeout = float(conf.get("source_timeout_seconds") or 15)
    source_collection_timeout = float(conf.get("source_collection_timeout_seconds") or 45)
    source_workers = max(1, int(conf.get("source_workers") or 5))
    max_source_chars = max(1000, int(conf.get("max_source_chars_per_video") or 16000))
    configured_min_similarity = conf.get("min_title_similarity")
    min_sim = float(
        0.95 if configured_min_similarity is None else configured_min_similarity
    )
    started = time.monotonic()
    deadline = started + timeout
    error: str | None = None
    search_succeeded = False
    collected: list[dict[str, Any]] = []
    videos: list[dict[str, Any]] = []
    videos_scanned = 0
    seen_q: set[str] = set()

    try:
        query = f"{job_title} interview questions answers Pakistan".strip()
        # Fetch more than max_videos then rank by embedding similarity
        raw_videos = search_youtube(
            query,
            max_results=max_search_results,
            timeout_seconds=min(15.0, max(1.0, deadline - time.monotonic())),
        )
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

        videos_scanned = len(videos)
        sources: list[dict[str, Any]] = []
        if videos:
            executor = ThreadPoolExecutor(
                max_workers=min(source_workers, len(videos)),
                thread_name_prefix="qna-source",
            )
            future_map = {
                executor.submit(
                    _collect_video_source,
                    video,
                    video_index=index,
                    max_comments=max_comments,
                    source_timeout_seconds=source_timeout,
                ): index
                for index, video in enumerate(videos, start=1)
            }
            remaining = max(1.0, deadline - time.monotonic() - 2)
            done, pending = wait(
                future_map,
                timeout=min(source_collection_timeout, remaining),
            )
            for future in pending:
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            for future in done:
                try:
                    sources.append(future.result())
                except Exception as exc:
                    logger.warning("qna_source_collection_failed error=%s", str(exc)[:200])
            sources.sort(key=lambda source: int(source["video_index"]))

        usable_sources = [
            source for source in sources if source.get("transcript") or source.get("comments")
        ]
        if videos and not usable_sources:
            error = (
                "Relevant YouTube videos were found, but their transcripts and comments "
                "could not be retrieved."
            )
        elif usable_sources:
            remaining = deadline - time.monotonic()
            if remaining <= 2:
                error = f"YouTube Q&A processing reached the {int(timeout)}-second limit."
            else:
                try:
                    pairs = extract_qna_from_sources(
                        job_title=job_title,
                        sources=usable_sources,
                        max_qna=max_qna,
                        max_source_chars_per_video=max_source_chars,
                        timeout_seconds=min(ai_timeout, max(1.0, remaining - 2)),
                    )
                    sources_by_index = {
                        int(source["video_index"]): source for source in usable_sources
                    }
                    for pair in pairs:
                        qkey = pair["question"].strip().lower()
                        if qkey in seen_q:
                            continue
                        seen_q.add(qkey)
                        source = sources_by_index[int(pair["video_index"])]
                        collected.append(
                            {
                                "question": pair["question"],
                                "answer": pair["answer"],
                                "source": pair.get("source"),
                                "youtube_url": source.get("url"),
                                "youtube_title": source.get("title"),
                            }
                        )
                        if len(collected) >= max_qna:
                            break
                except Exception as exc:
                    logger.exception("qna_combined_extraction_failed job_id=%s", job_id)
                    error = f"A YouTube or AI processing error occurred: {str(exc)[:300]}"
    except Exception as exc:
        logger.exception("fetch_qna_for_job_title failed job_id=%s", job_id)
        error = str(exc)

    collected = collected[:max_qna]
    saved: list[JobQnA] = []
    try:
        if not search_succeeded:
            raise RuntimeError(error or "YouTube search did not complete")
        if not collected:
            existing = (
                db.query(JobQnA)
                .filter(JobQnA.job_id == job_id)
                .order_by(JobQnA.created_at.asc())
                .all()
            )
            if not error:
                error = (
                    "No relevant question-and-answer pairs were found in matching "
                    "YouTube transcripts or comments."
                    if videos
                    else "No sufficiently relevant YouTube videos were found for this job title."
                )
            return {
                "items": existing,
                "count": 0,
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "error": error,
                "videos_scanned": videos_scanned,
            }
        # A valid partial result is a successful refresh. Do not surface an
        # earlier candidate-video error after useful Q&A has been collected.
        error = None
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

    elapsed = time.monotonic() - started
    return {
        "items": saved,
        "count": len(saved),
        "elapsed_seconds": round(elapsed, 2),
        "error": error,
        "videos_scanned": videos_scanned,
    }
