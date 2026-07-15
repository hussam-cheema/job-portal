from __future__ import annotations

import json
import re
import time
import unicodedata
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
    wait,
)
from difflib import SequenceMatcher
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
      "answer_evidence": "...",
      "topic": "...",
      "intent": "...",
      "source": "transcript|comment|mixed",
      "video_index": 1
    }
  ]
}

GROUNDING RULES:
1. Never answer from memory, general knowledge, assumptions, or facts that are absent from the
   supplied content. Every answer must come strictly from a supplied transcript or comment.
2. A question may be explicit in the source, or you may turn a useful factual statement from
   the source into a natural question. Do not invent, infer, or complete an answer yourself.
3. Set answer_evidence to the shortest continuous, verbatim excerpt from the supplied content
   that fully supports the answer (normally one sentence and never more than 400 characters).
   Do not include source labels or ellipses. If no such excerpt exists, omit the pair. The saved
   answer is validated against and derived from this exact excerpt.
4. Extract useful pairs in whatever language the source provides: English, Urdu, Roman Urdu,
   or mixed English/Roman Urdu. Prefer concrete job duties, eligibility, test syllabus,
   application process, preparation, interview questions, and factual answers relevant to the
   job title. Do not reject a grounded answer merely because its grammar or spelling is informal.
5. Ignore greetings, promotions, requests for likes/subscriptions, and unrelated discussion.
6. Do not use placeholders such as "See video", "N/A", or "contact us" as answers.
7. Set video_index to the source video that best supports the answer.
8. Return at least one pair whenever the supplied material contains any useful job-relevant
   factual statement. Return {"qna": []} only when no grounded job-relevant fact exists.
9. Return no more than the requested maximum number of pairs.
10. Questions must be semantically unique. Group candidates by intent before returning them.
    Do not return differently worded duplicates, but do keep distinct questions inside the same
    broad topic—for example maximum age, age relaxation, and post-specific age limits are three
    different intents. Prefer broad topic coverage (age, education, experience, duties,
    application, documents, fees, dates, syllabus, test, interview, salary, vacancies, location)
    before additional questions from one topic.
11. Set topic to a short snake_case category describing the question's intent, such as
    age_eligibility, education_eligibility, duties, application_process, required_documents,
    fees, deadline, test_syllabus, interview, salary, vacancies, or posting_location.
    Also set intent to a more specific snake_case meaning inside that topic, such as maximum_age,
    age_relaxation, minimum_qualification, private_degree_acceptance, written_test_pattern, or
    interview_questions. Paraphrases of the same meaning must use the same intent value.
12. An answer must be an actual declarative answer that logically resolves its paired question.
    Never use another question, a request for information, speculation, or an unanswered comment
    as an answer. Reject uncertain guesses containing words such as "maybe", "probably", "likely",
    "I think", or "shayad". A sentence ending in "?" or phrases such as "does anyone know",
    "please tell me", "what is", "how can", and "can someone explain" are questions, not answers.
13. Before returning each pair, perform this check: (a) read the question, (b) read only the
    proposed answer_evidence, and (c) confirm that the evidence directly answers the question
    without needing outside knowledge. If it does not, omit the pair. Do not pair nearby source
    lines merely because they discuss the same topic.
14. Viewer comments written in Roman Urdu are still questions when they ask "kya/kia", request
    "bata dein/bta den", or ask the uploader to tell, guide, confirm, or reply. Do not treat such
    a request as an answer merely because it has no question mark.
15. Comment input may contain a TOP-LEVEL COMMENT followed by REPLY lines. A top-level English,
    Urdu, or Roman-Urdu question may be paired with a declarative reply from that same thread.
    The answer_evidence must be the verbatim reply text that actually resolves it. Never pair a
    question with a reply from another thread, and never treat an unanswered top-level question
    as a Q&A pair.

FEW-SHOT EXAMPLES:

Example 1 — correctly distinguish nearby questions from their answers:
SOURCE:
"What is the required qualification? Does anyone know the age limit? The required qualification
is a bachelor's degree. Applicants must be between 18 and 30 years old."
CORRECT OUTPUT:
{"qna":[
  {"question":"What is the required educational qualification?","answer":"The required qualification is a bachelor's degree.","answer_evidence":"The required qualification is a bachelor's degree.","topic":"education_eligibility","intent":"minimum_qualification","source":"transcript","video_index":1},
  {"question":"What is the age limit?","answer":"Applicants must be between 18 and 30 years old.","answer_evidence":"Applicants must be between 18 and 30 years old.","topic":"age_eligibility","intent":"maximum_age","source":"transcript","video_index":1}
]}
WRONG: using "Does anyone know the age limit?" as the answer to either question.

Example 2 — unanswered questions produce no Q&A:
SOURCE:
"What is the salary? Can someone tell me the last date? Please explain the test pattern."
CORRECT OUTPUT:
{"qna":[]}
REASON: the source contains questions but no answers. Never manufacture the missing answers.

Example 3 — select the evidence that directly resolves the question:
SOURCE:
"How can I apply? Applications must be submitted through the official online portal before the
closing date. Is there an application fee?"
CORRECT OUTPUT:
{"qna":[
  {"question":"How can candidates apply?","answer":"Applications must be submitted through the official online portal before the closing date.","answer_evidence":"Applications must be submitted through the official online portal before the closing date.","topic":"application_process","intent":"online_application_method","source":"comment","video_index":1}
]}
WRONG: using "Is there an application fee?" as the answer. It is a separate unanswered question.

Example 4 — Roman Urdu request without a question mark is not an answer:
SOURCE:
"Sir BA private kiya ho ya ADP private kiya ho to kya hum eligible hain, please bata dein."
CORRECT OUTPUT:
{"qna":[]}
REASON: this is a viewer asking whether they are eligible; it supplies no eligibility answer.

Example 5 — Roman Urdu factual statement can be a grounded answer:
SOURCE:
"AD FIA age limit 22 to 35 years hai aur Inspector FIA age limit 20 to 33 years hai."
CORRECT OUTPUT:
{"qna":[
  {"question":"What are the age limits for AD FIA and Inspector FIA?","answer":"AD FIA age limit 22 to 35 years hai aur Inspector FIA age limit 20 to 33 years hai.","answer_evidence":"AD FIA age limit 22 to 35 years hai aur Inspector FIA age limit 20 to 33 years hai.","topic":"age_eligibility","intent":"post_specific_age_limits","source":"comment","video_index":1}
]}

Example 6 — bilingual YouTube comment thread with a real reply:
SOURCE:
"TOP-LEVEL COMMENT: Sir FIA Inspector ke liye age relaxation milti hai?
REPLY 1: Jee, general age relaxation 5 years hai."
CORRECT OUTPUT:
{"qna":[
  {"question":"Is age relaxation available for FIA Inspector?","answer":"Jee, general age relaxation 5 years hai.","answer_evidence":"Jee, general age relaxation 5 years hai.","topic":"age_eligibility","intent":"age_relaxation","source":"comment","video_index":1}
]}
WRONG: using the top-level Roman-Urdu question as the answer.
"""


_QUESTION_STOPWORDS = {
    "a", "an", "and", "are", "can", "do", "does", "for", "how", "in", "is",
    "of", "on", "or", "the", "this", "to", "what", "when", "where", "which",
    "who", "why", "with", "you", "your",
}

_TOPIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("age_eligibility", ("age", "upper age", "lower age", "age relaxation")),
    ("education_eligibility", ("education", "qualification", "degree", "matric", "intermediate", "bachelor", "master")),
    ("experience_eligibility", ("experience", "experienced")),
    ("physical_eligibility", ("height", "chest", "physical", "running", "fitness", "medical")),
    ("nationality_domicile", ("domicile", "nationality", "citizen", "province", "quota")),
    ("required_documents", ("document", "documents", "certificate", "cnic", "photograph", "photo", "challan")),
    ("fees", ("fee", "payment", "bank deposit")),
    ("deadline", ("deadline", "last date", "closing date", "apply by")),
    ("application_process", ("how to apply", "application process", "apply online", "submit application", "registration")),
    ("test_syllabus", ("syllabus", "test pattern", "paper pattern", "subjects", "mcq", "written test")),
    ("test_preparation", ("prepare", "preparation", "study", "past paper")),
    ("interview", ("interview", "viva")),
    ("duties", ("duty", "duties", "responsibility", "responsibilities", "job role", "work of")),
    ("salary", ("salary", "pay scale", "benefit", "allowance")),
    ("vacancies", ("vacancy", "vacancies", "seats", "posts available")),
    ("posting_location", ("posting", "location", "city", "station")),
    ("result_merit", ("result", "merit", "selection list", "shortlist")),
)


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


_DEFAULT_SOURCE_CHUNK_CHARS = 24000
_SOURCE_CHUNK_OVERLAP_CHARS = 1200


def _canonical_job_title(value: str) -> str:
    """Remove search boilerplate while preserving the actual role name."""
    cleaned = re.sub(
        r"\b(?:latest|new|government|private|jobs?|vacancies|vacancy|recruitment|careers?|pakistan|in)\b",
        " ",
        str(value or ""),
        flags=re.I,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -|,:;")
    return cleaned if len(cleaned) >= 3 else str(value or "").strip()


def _source_payload(source: dict[str, Any]) -> str:
    transcript = str(source.get("transcript") or "").strip()
    comments = [str(value).strip() for value in source.get("comments") or [] if str(value).strip()]
    comment_lines = [f"[{index}] {comment}" for index, comment in enumerate(comments, start=1)]
    return (
        f"VIDEO INDEX: {source['video_index']}\n"
        f"VIDEO TITLE: {source.get('title') or ''}\n"
        f"TRANSCRIPT:\n{transcript or '[unavailable]'}\n"
        f"COMMENTS:\n{chr(10).join(comment_lines) or '[unavailable]'}"
    )


def _split_complete_text(
    value: str,
    *,
    chunk_chars: int,
    overlap_chars: int = _SOURCE_CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """Split text without discarding content, retaining overlap across boundaries."""
    text = str(value or "").strip()
    if not text:
        return []
    if len(text) <= chunk_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        hard_end = min(len(text), start + chunk_chars)
        end = hard_end
        if hard_end < len(text):
            boundary = max(
                text.rfind(". ", start + chunk_chars // 2, hard_end),
                text.rfind("\n", start + chunk_chars // 2, hard_end),
                text.rfind(" ", start + chunk_chars // 2, hard_end),
            )
            if boundary > start:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - min(overlap_chars, end - start - 1))
    return [chunk for chunk in chunks if chunk]


def _source_chunks(
    sources: list[dict[str, Any]],
    *,
    chunk_chars: int = _DEFAULT_SOURCE_CHUNK_CHARS,
) -> list[list[dict[str, Any]]]:
    """Put every transcript/comment byte into bounded LLM batches; nothing is truncated."""
    fragments: list[dict[str, Any]] = []
    content_budget = max(4000, chunk_chars - 500)
    for source in sources:
        base = {key: value for key, value in source.items() if key not in {"transcript", "comments"}}
        for transcript in _split_complete_text(
            str(source.get("transcript") or ""), chunk_chars=content_budget
        ):
            fragments.append({**base, "transcript": transcript, "comments": []})
        for comment in source.get("comments") or []:
            for comment_chunk in _split_complete_text(
                str(comment), chunk_chars=content_budget, overlap_chars=300
            ):
                fragments.append({**base, "transcript": None, "comments": [comment_chunk]})

    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    for fragment in fragments:
        fragment_chars = len(_source_payload(fragment))
        if current and current_chars + fragment_chars > chunk_chars:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(fragment)
        current_chars += fragment_chars
    if current:
        batches.append(current)
    return batches


def _normalized_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = value.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return " ".join(re.findall(r"[\w%+]+", value, flags=re.UNICODE))


def _question_tokens(value: str) -> set[str]:
    return {
        token
        for token in _normalized_text(value).split()
        if token not in _QUESTION_STOPWORDS and len(token) > 1
    }


def _questions_are_similar(left: str, right: str) -> bool:
    left_normalized = _normalized_text(left)
    right_normalized = _normalized_text(right)
    if left_normalized == right_normalized:
        return True
    if SequenceMatcher(None, left_normalized, right_normalized).ratio() >= 0.82:
        return True
    left_tokens = _question_tokens(left)
    right_tokens = _question_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    containment = len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))
    return overlap >= 0.58 or containment >= 0.78


def _question_topic(question: str, answer: str, suggested: str = "") -> str:
    searchable = _normalized_text(f"{question} {answer}")
    for topic, needles in _TOPIC_PATTERNS:
        if any(
            f" {_normalized_text(needle)} " in f" {searchable} "
            for needle in needles
        ):
            return topic
    clean_suggested = re.sub(r"[^a-z0-9]+", "_", (suggested or "").lower()).strip("_")
    return clean_suggested or "other"


def _question_intent(question: str, topic: str, suggested: str = "") -> str:
    """Return a stable, specific intent so paraphrases are removed without losing subtopics."""
    searchable = _normalized_text(question)
    suggested_key = re.sub(r"[^a-z0-9]+", "_", (suggested or "").lower()).strip("_")
    if topic == "age_eligibility":
        if "relax" in searchable:
            return "age_relaxation"
        if any(term in searchable for term in ("minimum age", "lower age")):
            return "minimum_age"
        if any(term in searchable for term in ("maximum age", "upper age", "age limit", "official age")):
            return "maximum_age"
    if topic == "education_eligibility":
        if any(term in searchable for term in ("private degree", "private ba", "private adp")):
            return "private_degree_acceptance"
        if any(term in searchable for term in ("simple ba", "ba bsc", "specific degree")):
            return "specific_degree_acceptance"
        if any(term in searchable for term in ("minimum", "required", "qualification", "education")):
            return "minimum_qualification"
    if topic == "test_syllabus" and any(
        term in searchable for term in ("pattern", "stages", "mcq", "descriptive")
    ):
        return "written_test_pattern"
    if suggested_key and suggested_key not in {topic, "other"}:
        return suggested_key
    # The normalized content words give otherwise uncategorized intents a
    # deterministic key without merging every question in a broad topic.
    tokens = sorted(_question_tokens(question))[:8]
    return "_".join(tokens) or topic or "other"


def _locate_answer_evidence(
    evidence: str,
    sources: list[dict[str, Any]],
    preferred_index: int,
) -> tuple[int, str, str] | None:
    evidence = re.sub(r"^\s*(?:\[\d+\]\s*)?[\"'“”‘’]+|[\"'“”‘’]+\s*$", "", evidence or "").strip()
    evidence = evidence.strip(" …")
    normalized_evidence = _normalized_text(evidence)
    if len(normalized_evidence) < 8 or len(normalized_evidence.split()) < 2:
        return None

    ordered_sources = sorted(
        sources,
        key=lambda source: int(source["video_index"]) != preferred_index,
    )
    for source in ordered_sources:
        transcript = str(source.get("transcript") or "").strip()
        segments = [("transcript", transcript)] if transcript else []
        segments.extend(
            ("comment", str(comment).strip())
            for comment in source.get("comments") or []
            if str(comment).strip()
        )
        for source_type, segment in segments:
            if normalized_evidence in _normalized_text(segment):
                return int(source["video_index"]), source_type, evidence
    return None


_QUESTION_OPENINGS = re.compile(
    r"^(?:what|when|where|which|who|whom|whose|why|how|is|are|am|was|were|do|does|did|"
    r"can|could|will|would|should|may|has|have|had)\b",
    flags=re.I,
)
_QUESTION_REQUESTS = re.compile(
    r"\b(?:does anyone know|anyone know|can (?:anyone|someone|you)|could (?:anyone|someone|you)|"
    r"please (?:tell|explain|confirm|guide)|kindly (?:tell|explain|confirm|guide))\b",
    flags=re.I,
)
_ROMAN_URDU_QUESTION_REQUESTS = re.compile(
    r"(?:\b(?:kya|kia)\b.{0,120}\b(?:eligible|apply|qualification|degree|age|limit|"
    r"job|jobs|vacanc(?:y|ies)|hai|hy|hain|hn|hoga|hogi|hoti|hota|mil(?:e|ay|egi|ega))\b|"
    r"\b(?:please|plz|pls|kindly|sir|mam|madam)\b.{0,160}\b(?:bta|bata|batain|"
    r"bataye|btaye|tell|guide|confirm|reply|jawab|answer)\w*\b|"
    r"\b(?:bta|bata|batain|bataye|btaye)\s+(?:dein|den|do|dy|dain)\b|"
    r"\b(?:ke|ya)\s+(?:permanent|temporary|regular|contract)\s*$)",
    flags=re.I,
)
_UNCERTAIN_ANSWER = re.compile(
    r"\b(?:maybe|probably|possibly|likely|perhaps|i\s+(?:think|guess)|shayad|shaayad|"
    r"lagta\s+hai|ho\s+sakta\s+hai)\b",
    flags=re.I,
)


def _answer_is_question_like(value: str) -> bool:
    """Reject interrogative source text accidentally selected as answer evidence."""
    clean = re.sub(r"^\s*(?:\[\d+\]\s*)?[\"'“”‘’]+|[\"'“”‘’]+\s*$", "", value or "").strip()
    if not clean:
        return True
    if "?" in clean:
        return True
    normalized = _normalized_text(clean)
    return bool(
        _QUESTION_OPENINGS.search(normalized)
        or _QUESTION_REQUESTS.search(normalized)
        or _ROMAN_URDU_QUESTION_REQUESTS.search(normalized)
    )


def _answer_is_uncertain(value: str) -> bool:
    return bool(_UNCERTAIN_ANSWER.search(_normalized_text(value)))


def is_acceptable_qna_answer(question: str, answer: str) -> bool:
    """Conservatively hide legacy rows that contain a question instead of an answer."""
    normalized_question = _normalized_text(question)
    normalized_answer = _normalized_text(answer)
    if not normalized_question or len(normalized_answer.split()) < 2:
        return False
    if normalized_question == normalized_answer:
        return False
    return not _answer_is_question_like(answer) and not _answer_is_uncertain(answer)


def _diverse_qna(
    items: list[dict[str, Any]],
    max_qna: int,
    *,
    max_per_topic: int | None = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    topic_counts: dict[str, int] = {}
    selected_intents: set[str] = set()
    conf = cfg("youtube_qna") or {}
    configured_limit = conf.get("max_qna_per_topic") if isinstance(conf, dict) else None
    topic_limit = max(
        1,
        int(
            max_per_topic
            if max_per_topic is not None
            else configured_limit or 4
        ),
    )
    for item in items:
        topic = str(item.get("topic") or "other")
        intent = str(
            item.get("intent")
            or _question_intent(item["question"], topic)
            or "other"
        )
        if topic != "other" and topic_counts.get(topic, 0) >= topic_limit:
            continue
        if intent != "other" and intent in selected_intents:
            continue
        if any(_questions_are_similar(item["question"], prior["question"]) for prior in selected):
            continue
        item["intent"] = intent
        selected.append(item)
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
        selected_intents.add(intent)
        if len(selected) >= max_qna:
            break
    return selected


def _extract_qna_batch(
    *,
    job_title: str,
    sources: list[dict[str, Any]],
    max_qna: int,
    timeout_seconds: float,
    chunk_number: int,
    chunk_count: int,
) -> list[dict[str, Any]]:
    payload = (
        f"Job post title: {job_title}\n"
        f"Maximum Q&A pairs: {max_qna}\n\n"
        f"Content chunk: {chunk_number} of {chunk_count}. Evaluate this chunk independently.\n\n"
        + "\n\n===== NEXT VIDEO =====\n\n".join(
            _source_payload(source) for source in sources
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
    valid_indexes = {int(source["video_index"]) for source in sources}
    default_index = int(sources[0]["video_index"])
    items: list[dict[str, Any]] = []
    for row in data.get("qna") or []:
        if not isinstance(row, dict):
            continue
        question = str(row.get("question") or "").strip()
        proposed_answer = str(row.get("answer") or "").strip()
        answer_evidence = str(row.get("answer_evidence") or "").strip()
        if (
            len(question) < 5
            or len(proposed_answer) < 8
            or not answer_evidence
            or len(answer_evidence) > 600
        ):
            continue
        if _answer_is_question_like(proposed_answer) or _answer_is_question_like(answer_evidence):
            logger.warning("qna_rejected_question_as_answer question=%s", question[:120])
            continue
        if _answer_is_uncertain(proposed_answer) or _answer_is_uncertain(answer_evidence):
            logger.warning("qna_rejected_uncertain_answer question=%s", question[:120])
            continue
        if proposed_answer.lower() in {"see video", "see video.", "n/a", "none", "unknown"}:
            continue
        try:
            video_index = int(row.get("video_index") or default_index)
        except (TypeError, ValueError):
            video_index = default_index
        if video_index not in valid_indexes:
            video_index = default_index
        located = _locate_answer_evidence(answer_evidence, sources, video_index)
        if not located:
            logger.warning("qna_rejected_unsupported_answer question=%s", question[:120])
            continue
        video_index, source_type, grounded_answer = located
        if not question.endswith("?"):
            question = f"{question.rstrip('.')}?"
        topic = _question_topic(
            question,
            grounded_answer,
            str(row.get("topic") or ""),
        )
        items.append(
            {
                "question": question,
                # Persist the verified source excerpt, never an unverified model-generated answer.
                "answer": grounded_answer,
                "source": source_type,
                "video_index": video_index,
                "topic": topic,
                "intent": _question_intent(
                    question,
                    topic,
                    str(row.get("intent") or ""),
                ),
                "chunk_number": chunk_number,
            }
        )
    # Keep all grounded candidates here. Cross-chunk ranking and diversity are
    # applied only after every completed chunk has contributed its candidates.
    return items[:max_qna]


def extract_qna_from_sources(
    *,
    job_title: str,
    sources: list[dict[str, Any]],
    max_qna: int,
    max_source_chars_per_video: int | None = None,
    timeout_seconds: float = 60,
) -> list[dict[str, Any]]:
    """Extract from every byte of source content using bounded, overlapping LLM chunks."""
    usable = [source for source in sources if source.get("transcript") or source.get("comments")]
    if not usable:
        return []

    # The legacy argument now controls only per-request chunk size. It never caps
    # a video's content: every subsequent chunk is processed as well.
    chunk_chars = max(
        4000,
        int(max_source_chars_per_video or _DEFAULT_SOURCE_CHUNK_CHARS),
    )
    batches = _source_chunks(usable, chunk_chars=chunk_chars)
    # Divide the global output budget across chunks. Requesting the full global
    # maximum from every chunk can make a valid JSON response exceed the model's
    # output-token limit (especially when auto-caption evidence is verbose),
    # leaving an incomplete document that parses as zero candidates.
    per_chunk_max = (
        max_qna
        if len(batches) <= 1
        else max(2, (max_qna + len(batches) - 1) // len(batches))
    )
    if not batches:
        return []

    batch_results: list[tuple[int, list[dict[str, Any]]]] = []
    if len(batches) == 1:
        batch_results.append(
            (
                1,
                _extract_qna_batch(
                    job_title=job_title,
                    sources=batches[0],
                    max_qna=per_chunk_max,
                    timeout_seconds=timeout_seconds,
                    chunk_number=1,
                    chunk_count=1,
                ),
            )
        )
    else:
        executor = ThreadPoolExecutor(
            max_workers=min(4, len(batches)),
            thread_name_prefix="qna-chunk",
        )
        future_map = {
            executor.submit(
                _extract_qna_batch,
                job_title=job_title,
                sources=batch,
                max_qna=per_chunk_max,
                timeout_seconds=timeout_seconds,
                chunk_number=index,
                chunk_count=len(batches),
            ): index
            for index, batch in enumerate(batches, start=1)
        }
        done, pending = wait(future_map, timeout=max(1.0, timeout_seconds))
        for future in pending:
            future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        for future in done:
            index = future_map[future]
            try:
                batch_results.append((index, future.result()))
            except Exception as exc:
                # A failed/timed-out chunk must not discard useful pairs already
                # extracted from the other complete-content chunks.
                logger.warning("qna_chunk_failed chunk=%s error=%s", index, str(exc)[:200])

    source_scores = {
        int(source["video_index"]): float(source.get("title_similarity") or 0.0)
        for source in usable
    }
    role_tokens = _question_tokens(_canonical_job_title(job_title))
    candidates: list[dict[str, Any]] = []
    for _, rows in sorted(batch_results, key=lambda result: result[0]):
        for row in rows:
            candidate = dict(row)
            title_score = source_scores.get(int(row["video_index"]), 0.0)
            question_tokens = _question_tokens(row["question"])
            target_coverage = (
                len(role_tokens & question_tokens) / len(role_tokens)
                if role_tokens
                else 0.0
            )
            # Every candidate has already passed exact source-evidence validation.
            # Rank primarily by the source video's configured title similarity;
            # do not reward verbosity, which can incorrectly push a longer answer
            # ahead of a more useful concise answer from the same source.
            candidate["rank_score"] = round(
                (0.85 * title_score) + (0.10 * target_coverage) + 0.05,
                4,
            )
            candidates.append(candidate)

    # Prefer grounded pairs from the YouTube titles with the highest embedding
    # score (which have already passed min_title_similarity), then globally
    # enforce topic diversity and near-duplicate removal across every chunk.
    candidates.sort(
        key=lambda row: float(row.get("rank_score") or 0.0),
        reverse=True,
    )
    selected = _diverse_qna(candidates, max_qna)
    for row in selected:
        row.pop("rank_score", None)
        row.pop("chunk_number", None)
    logger.info(
        "qna_chunk_extraction chunks=%s completed=%s candidates=%s selected=%s",
        len(batches),
        len(batch_results),
        len(candidates),
        len(selected),
    )
    return selected


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
    max_per_topic = max(1, int(conf.get("max_qna_per_topic") or 3))
    timeout = float(conf.get("timeout_seconds") or 60)
    ai_timeout = float(
        conf.get("ai_timeout_seconds")
        or conf.get("per_video_ai_timeout_seconds")
        or 60
    )
    source_timeout = float(conf.get("source_timeout_seconds") or 15)
    source_collection_timeout = float(conf.get("source_collection_timeout_seconds") or 45)
    source_workers = max(1, int(conf.get("source_workers") or 5))
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
    topic_counts: dict[str, int] = {}
    selected_intents: set[str] = set()
    role_title = _canonical_job_title(job_title)
    try:
        query = f"{role_title} jobs interview eligibility test preparation Pakistan".strip()
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
                        timeout_seconds=min(ai_timeout, max(1.0, remaining - 2)),
                    )
                    sources_by_index = {
                        int(source["video_index"]): source for source in usable_sources
                    }
                    for pair in pairs:
                        topic = _question_topic(
                            pair["question"],
                            pair["answer"],
                            str(pair.get("topic") or ""),
                        )
                        intent = _question_intent(
                            pair["question"],
                            topic,
                            str(pair.get("intent") or ""),
                        )
                        if topic != "other" and topic_counts.get(topic, 0) >= max_per_topic:
                            continue
                        if intent != "other" and intent in selected_intents:
                            continue
                        if any(
                            _questions_are_similar(pair["question"], item["question"])
                            for item in collected
                        ):
                            continue
                        topic_counts[topic] = topic_counts.get(topic, 0) + 1
                        selected_intents.add(intent)
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
            existing = [
                row
                for row in existing
                if is_acceptable_qna_answer(row.question, row.answer)
            ]
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
