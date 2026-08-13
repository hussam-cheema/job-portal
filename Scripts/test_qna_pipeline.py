#!/usr/bin/env python3
"""Live, test-only diagnostics for the four-stage YouTube Q&A pipeline.

This script intentionally orchestrates and reports the stages itself.  No
diagnostic payload or UI is exposed by the application API.
"""
from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import CheckFailed, add_backend_to_path, config, run


def check() -> str:
    parser = argparse.ArgumentParser(
        description="Test YouTube search, sources, chunking, and DeepSeek extraction."
    )
    parser.add_argument("--title", default="FIA Inspector in FPSC")
    args = parser.parse_args()

    add_backend_to_path()
    from app.services.embeddings import rank_by_similarity
    from app.services.qna import (
        _canonical_job_title,
        _collect_video_source,
        _diverse_qna,
        _extract_qna_batch,
        _question_tokens,
        _source_chunks,
    )
    from app.services.youtube import search_youtube

    title = args.title.strip()
    max_qna = int(config("youtube_qna", "max_qna", default=20) or 20)
    max_videos = int(config("youtube_qna", "max_youtube_videos", default=5) or 5)
    max_search = int(
        config("youtube_qna", "max_youtube_search_results", default=5) or 5
    )
    max_search = min(max_search, max_videos)
    max_comments = int(config("youtube_qna", "max_comments", default=50) or 50)
    min_similarity = float(
        config("youtube_qna", "min_title_similarity", default=0.8) or 0.8
    )
    source_timeout = float(
        config("youtube_qna", "source_timeout_seconds", default=15) or 15
    )
    ai_timeout = float(
        config("youtube_qna", "ai_timeout_seconds", default=60) or 60
    )
    started = time.monotonic()

    # 1. Search and independently verify configured similarity filtering.
    query = (
        f"{_canonical_job_title(title)} jobs interview eligibility test "
        "preparation Pakistan"
    )
    raw_videos = search_youtube(
        query,
        max_results=max_search,
        timeout_seconds=15,
        raise_on_failure=True,
    )
    ranked = rank_by_similarity(
        title,
        raw_videos,
        key="title",
        score_key="title_similarity",
        raw_cosine_only=True,
        preserve_order=True,
    )
    videos = [
        video
        for video in ranked
        if float(video.get("title_similarity") or 0) >= min_similarity
    ][:max_videos]
    if not videos:
        top = ", ".join(
            f"{row.get('title')}={float(row.get('title_similarity') or 0):.4f}"
            for row in ranked[:5]
        )
        raise CheckFailed(
            f"Check 1 failed: no video met {min_similarity:.2f}. Top scores: {top}"
        )
    print(
        f"[PASS 1/4] similarity search: {len(raw_videos)} searched; "
        f"{len(videos)} selected at >= {min_similarity:.2f}"
    )
    for index, video in enumerate(videos, start=1):
        print(
            f"  video={index} score={float(video.get('title_similarity') or 0):.4f} "
            f"title={video.get('title')}"
        )

    # 2. Fetch transcripts/comments from precisely the videos that passed.
    sources = []
    with ThreadPoolExecutor(max_workers=min(5, len(videos))) as executor:
        futures = {
            executor.submit(
                _collect_video_source,
                video,
                video_index=index,
                max_comments=max_comments,
                source_timeout_seconds=source_timeout,
            ): index
            for index, video in enumerate(videos, start=1)
        }
        for future in as_completed(futures):
            sources.append(future.result())
    sources.sort(key=lambda source: int(source["video_index"]))
    usable = [source for source in sources if source.get("transcript") or source.get("comments")]
    if not usable:
        raise CheckFailed("Check 2 failed: selected videos supplied no transcript or comments")
    print(
        f"[PASS 2/4] scripts/comments: {len(usable)} of {len(videos)} videos supplied content"
    )
    for source in sources:
        print(
            f"  video={source['video_index']} transcript_chars="
            f"{len(str(source.get('transcript') or ''))} comments="
            f"{len(source.get('comments') or [])}"
        )

    # 3. Verify complete-content chunks are produced without a production API trace.
    chunks = _source_chunks(usable)
    if not chunks:
        raise CheckFailed("Check 3 failed: no complete-content chunks were created")
    print(f"[PASS 3/4] chunking: {len(chunks)} complete-content chunk(s) created")

    # 4. Ask DeepSeek for candidates from every chunk, then apply the same ranking
    # and diversity policy as the application while reporting test-only evidence.
    per_chunk_max = (
        max_qna
        if len(chunks) == 1
        else max(2, (max_qna + len(chunks) - 1) // len(chunks))
    )
    source_scores = {
        int(source["video_index"]): float(source.get("title_similarity") or 0)
        for source in usable
    }
    role_tokens = _question_tokens(_canonical_job_title(title))
    candidates = []
    for chunk_number, chunk in enumerate(chunks, start=1):
        rows = _extract_qna_batch(
            job_title=title,
            sources=chunk,
            max_qna=per_chunk_max,
            timeout_seconds=ai_timeout,
            chunk_number=chunk_number,
            chunk_count=len(chunks),
        )
        for row in rows:
            candidate = dict(row)
            question_tokens = _question_tokens(row["question"])
            target_coverage = (
                len(role_tokens & question_tokens) / len(role_tokens)
                if role_tokens
                else 0.0
            )
            candidate["rank_score"] = round(
                0.85 * source_scores.get(int(row["video_index"]), 0)
                + 0.10 * target_coverage
                + 0.05,
                4,
            )
            candidates.append(candidate)
        print(f"  chunk={chunk_number} candidates={len(rows)}")
        for row in rows:
            question_tokens = _question_tokens(row["question"])
            target_coverage = (
                len(role_tokens & question_tokens) / len(role_tokens)
                if role_tokens
                else 0.0
            )
            score = (
                0.85 * source_scores.get(int(row["video_index"]), 0)
                + 0.10 * target_coverage
                + 0.05
            )
            print(
                f"    score={score:.4f} video={row['video_index']} "
                f"question={row['question']}"
            )
    candidates.sort(key=lambda row: float(row.get("rank_score") or 0), reverse=True)
    selected = _diverse_qna(candidates, max_qna)
    if not selected:
        raise CheckFailed(
            "Check 4 failed: DeepSeek returned no grounded Q&A candidate from any chunk"
        )
    print(
        f"[PASS 4/4] DeepSeek extraction/ranking: {len(candidates)} candidate(s); "
        f"{len(selected)} selected"
    )
    for row in selected:
        print(
            f"  SELECTED chunk={row.get('chunk_number')} video={row['video_index']} "
            f"score={float(row.get('rank_score') or 0):.4f}\n"
            f"    Q: {row['question']}\n"
            f"    A: {row['answer']}"
        )

    elapsed = time.monotonic() - started
    return f"all four test-only pipeline checks passed in {elapsed:.2f}s"


if __name__ == "__main__":
    raise SystemExit(run(check))
