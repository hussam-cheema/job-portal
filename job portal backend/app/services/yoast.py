from __future__ import annotations

import re
from typing import Any

from app.utils import strip_html


def analyze_yoast(
    *,
    title: str,
    content_html: str,
    meta_title: str | None,
    meta_description: str | None,
    focus_keyword: str | None,
    slug: str | None = None,
) -> dict[str, Any]:
    """
    Yoast-style on-page SEO + readability checks (client-compatible rules, pure Python).
    Returns scores 0-100 and traffic-light checks.
    """
    text = strip_html(content_html or "")
    words = re.findall(r"[A-Za-z0-9']+", text)
    word_count = len(words)
    fk = (focus_keyword or "").strip().lower()
    mt = (meta_title or title or "").strip()
    md = (meta_description or "").strip()
    slug_s = (slug or "").lower()

    checks: list[dict[str, Any]] = []

    def add(key: str, label: str, status: str, score: int, tip: str):
        checks.append(
            {"key": key, "label": label, "status": status, "score": score, "tip": tip}
        )

    # --- SEO checks ---
    if fk:
        in_title = fk in mt.lower()
        add(
            "kw_title",
            "Focus keyphrase in SEO title",
            "good" if in_title else "bad",
            100 if in_title else 20,
            "Include the focus keyphrase near the start of the SEO title.",
        )
        in_meta = fk in md.lower() if md else False
        add(
            "kw_meta",
            "Focus keyphrase in meta description",
            "good" if in_meta else ("ok" if md else "bad"),
            100 if in_meta else (50 if md else 10),
            "Mention the keyphrase naturally in the meta description.",
        )
        in_body = fk in text.lower()
        density = (text.lower().count(fk) / max(word_count, 1)) * 100 if fk else 0
        if in_body and 0.5 <= density <= 3.0:
            add("kw_density", "Keyphrase density", "good", 100, f"Density ~{density:.1f}% (ideal 0.5–3%).")
        elif in_body:
            add(
                "kw_density",
                "Keyphrase density",
                "ok",
                60,
                f"Density ~{density:.1f}%. Aim for 0.5–3%.",
            )
        else:
            add("kw_density", "Keyphrase density", "bad", 15, "Use the focus keyphrase in the content.")
        if slug_s:
            slug_ok = fk.replace(" ", "-") in slug_s or all(
                p in slug_s for p in fk.split() if len(p) > 2
            )
            add(
                "kw_slug",
                "Keyphrase in slug",
                "good" if slug_ok else "ok",
                90 if slug_ok else 55,
                "Include keyphrase words in the URL slug.",
            )
    else:
        add("kw_missing", "Focus keyphrase", "bad", 0, "Set a focus keyphrase for better SEO targeting.")

    tlen = len(mt)
    if 30 <= tlen <= 60:
        add("title_len", "SEO title length", "good", 100, f"{tlen} chars (ideal 30–60).")
    elif 20 <= tlen < 30 or 60 < tlen <= 70:
        add("title_len", "SEO title length", "ok", 65, f"{tlen} chars — aim for 30–60.")
    else:
        add("title_len", "SEO title length", "bad", 25, f"{tlen} chars — aim for 30–60.")

    dlen = len(md)
    if 120 <= dlen <= 160:
        add("meta_len", "Meta description length", "good", 100, f"{dlen} chars (ideal 120–160).")
    elif 70 <= dlen < 120 or 160 < dlen <= 200:
        add("meta_len", "Meta description length", "ok", 60, f"{dlen} chars — aim for 120–160.")
    else:
        add(
            "meta_len",
            "Meta description length",
            "bad",
            20 if dlen else 0,
            "Write a meta description of about 120–160 characters.",
        )

    if word_count >= 300:
        add("length", "Content length", "good", 100, f"{word_count} words.")
    elif word_count >= 150:
        add("length", "Content length", "ok", 55, f"{word_count} words — aim for 300+.")
    else:
        add("length", "Content length", "bad", 20, f"Only {word_count} words — add more content.")

    has_h = bool(re.search(r"<h[1-3][^>]*>", content_html or "", re.I))
    add(
        "headings",
        "Subheadings",
        "good" if has_h else "ok",
        90 if has_h else 50,
        "Use H2/H3 headings to structure content." if not has_h else "Headings present.",
    )

    img_count = len(re.findall(r"<img\b", content_html or "", re.I))
    add(
        "images",
        "Images",
        "good" if img_count else "ok",
        85 if img_count else 50,
        "Consider adding images with descriptive alt text." if not img_count else f"{img_count} image(s).",
    )

    # --- Readability ---
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    avg_sent = (word_count / max(len(sentences), 1)) if sentences else word_count
    if avg_sent <= 20:
        add("sentence_len", "Sentence length", "good", 100, f"Avg ~{avg_sent:.0f} words/sentence.")
    elif avg_sent <= 25:
        add("sentence_len", "Sentence length", "ok", 60, f"Avg ~{avg_sent:.0f} — try shorter sentences.")
    else:
        add("sentence_len", "Sentence length", "bad", 30, f"Avg ~{avg_sent:.0f} — sentences are long.")

    paras = [p for p in re.split(r"\n\s*\n|</p>", content_html or "") if strip_html(p).strip()]
    long_paras = sum(1 for p in paras if len(strip_html(p).split()) > 150)
    add(
        "paragraphs",
        "Paragraph length",
        "good" if long_paras == 0 else "ok",
        90 if long_paras == 0 else 50,
        "Break up long paragraphs." if long_paras else "Paragraphs look manageable.",
    )

    seo_items = [c for c in checks if c["key"] not in {"sentence_len", "paragraphs"}]
    read_items = [c for c in checks if c["key"] in {"sentence_len", "paragraphs", "length", "headings"}]
    seo_score = round(sum(c["score"] for c in seo_items) / max(len(seo_items), 1), 1)
    read_score = round(sum(c["score"] for c in read_items) / max(len(read_items), 1), 1)

    def traffic(score: float) -> str:
        if score >= 75:
            return "good"
        if score >= 50:
            return "ok"
        return "bad"

    return {
        "seo_score": seo_score,
        "readability_score": read_score,
        "seo_status": traffic(seo_score),
        "readability_status": traffic(read_score),
        "word_count": word_count,
        "checks": checks,
        "snippet": {
            "title": mt[:70] or "SEO title preview",
            "description": md[:160] or "Meta description preview appears here.",
            "url": f"https://example.com/{slug_s or 'url-slug'}",
        },
    }
