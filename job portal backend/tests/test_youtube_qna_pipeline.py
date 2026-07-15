from __future__ import annotations

import json
import math

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import JobQnA


def test_fia_inspector_pipeline_passes_all_four_stages(monkeypatch):
    """Exercise search, source collection, chunking, extraction, ranking, and persistence."""
    from app.services import embeddings, qna

    engine = create_engine("sqlite://", poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Session()

    configuration = {
        "max_qna": 10,
        "max_youtube_videos": 5,
        "max_youtube_search_results": 50,
        "max_comments": 50,
        "min_title_similarity": 0.70,
        "timeout_seconds": 30,
        "ai_timeout_seconds": 10,
        "source_timeout_seconds": 5,
        "source_collection_timeout_seconds": 10,
        "source_workers": 2,
    }
    monkeypatch.setattr(qna, "cfg", lambda *_keys, **_kwargs: configuration)
    monkeypatch.setattr(qna, "_DEFAULT_SOURCE_CHUNK_CHARS", 4000)

    videos = [
        {
            "video_id": "fia-eligibility",
            "title": "FIA Inspector Jobs Eligibility and Written Test Guide",
            "url": "https://youtu.be/fia-eligibility",
        },
        {
            "video_id": "fia-application",
            "title": "How to Apply for FIA Inspector Recruitment",
            "url": "https://youtu.be/fia-application",
        },
        {
            "video_id": "generic",
            "title": "General Career Advice for Students",
            "url": "https://youtu.be/generic",
        },
    ]

    def search(_query, **kwargs):
        assert kwargs["max_results"] == 50
        return videos

    monkeypatch.setattr(qna, "search_youtube", search)

    # EmbeddingGemma commonly gives related short titles a raw cosine near
    # 0.5-0.6. The production calibration must let role-token matches clear a
    # configured 0.70 threshold without admitting a generic careers video.
    def semantic_vectors(texts, *, query_first=False):
        assert query_first is True
        values = [[1.0, 0.0]]
        for text in texts[1:]:
            raw_cosine = 0.58 if "fia" in text.lower() and "inspector" in text.lower() else 0.10
            values.append([raw_cosine, math.sqrt(1.0 - raw_cosine**2)])
        return values

    monkeypatch.setattr(embeddings, "_semantic_embeddings", semantic_vectors)

    age_evidence = "Applicants must be between 20 and 28 years old."
    education_evidence = "Candidates must hold at least a bachelor's degree."
    application_evidence = "Applications must be submitted through the official FIA portal."
    transcripts = {
        "fia-eligibility": (
            ("This section explains FIA Inspector preparation and the written test. " * 90)
            + age_evidence
            + " "
            + education_evidence
        ),
        "fia-application": (
            ("This section describes FIA Inspector recruitment and documents. " * 90)
            + application_evidence
        ),
    }
    monkeypatch.setattr(qna, "get_transcript", lambda video_id: transcripts.get(video_id))
    monkeypatch.setattr(
        qna,
        "get_top_comments",
        lambda video_id, **_kwargs: [
            "The written test includes English, general knowledge, and current affairs."
        ]
        if video_id != "generic"
        else [],
    )

    def deepseek(messages, **_kwargs):
        prompt = messages[-1]["content"]
        rows = []
        evidence_rows = [
            (
                age_evidence,
                "What is the age requirement?",
                "age_eligibility",
            ),
            (
                education_evidence,
                "What education is required?",
                "education_eligibility",
            ),
            (
                application_evidence,
                "How should candidates apply?",
                "application_process",
            ),
        ]
        for evidence, question, topic in evidence_rows:
            if evidence in prompt:
                rows.append(
                    {
                        "question": question,
                        "answer": evidence,
                        "answer_evidence": evidence,
                        "topic": topic,
                        "source": "transcript",
                        "video_index": 2 if evidence == application_evidence else 1,
                    }
                )
        return json.dumps({"qna": rows})

    monkeypatch.setattr(qna, "chat_completion", deepseek)

    try:
        # Each diagnostic assertion is intentionally test-only.  The app/API
        # response does not expose a pipeline trace.
        ranked = embeddings.rank_by_similarity(
            "FIA Inspector jobs in government",
            videos,
            key="title",
            score_key="title_similarity",
        )
        selected_videos = [
            row
            for row in ranked
            if float(row.get("title_similarity") or 0)
            >= configuration["min_title_similarity"]
        ][: configuration["max_youtube_videos"]]
        assert len(selected_videos) == 2  # check 1: similarity search
        assert all(row["video_id"] != "generic" for row in selected_videos)

        sources = [
            qna._collect_video_source(
                video,
                video_index=index,
                max_comments=configuration["max_comments"],
                source_timeout_seconds=configuration["source_timeout_seconds"],
            )
            for index, video in enumerate(selected_videos, start=1)
        ]
        assert all(source.get("transcript") or source.get("comments") for source in sources)
        # check 2: transcript/comment collection

        chunks = qna._source_chunks(sources, chunk_chars=4000)
        assert len(chunks) >= 2  # check 3: complete-content chunking

        extracted = qna.extract_qna_from_sources(
            job_title="FIA Inspector jobs in government",
            sources=sources,
            max_qna=configuration["max_qna"],
            max_source_chars_per_video=4000,
            timeout_seconds=configuration["ai_timeout_seconds"],
        )
        assert len(extracted) >= 3  # check 4: extraction and ranking

        result = qna.fetch_qna_for_job_title(
            db,
            job_id="fia-inspector-test",
            job_title="FIA Inspector jobs in government",
        )
        assert result["count"] >= 3
        assert "pipeline" not in result

        persisted = (
            db.query(JobQnA)
            .filter(JobQnA.job_id == "fia-inspector-test")
            .count()
        )
        assert persisted == result["count"]
        assert result["error"] is None
    finally:
        db.close()
