"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api";
import { getAdminToken } from "@/lib/adminAuth";

export type YoastSEOValue = {
  focus_keyword: string;
  meta_title: string;
  meta_description: string;
  meta_keywords: string;
};

type Analysis = {
  seo_score: number;
  readability_score: number;
  seo_status: string;
  readability_status: string;
  word_count: number;
  checks: Array<{
    key: string;
    label: string;
    status: string;
    score: number;
    tip: string;
  }>;
  snippet: { title: string; description: string; url: string };
};

type Props = {
  title: string;
  content: string;
  slug?: string;
  value: YoastSEOValue;
  onChange: (v: YoastSEOValue) => void;
};

function light(status: string) {
  if (status === "good") return "yoast-good";
  if (status === "ok") return "yoast-ok";
  return "yoast-bad";
}

export function YoastSEOPanel({ title, content, slug, value, onChange }: Props) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [analysisError, setAnalysisError] = useState("");

  const payload = useMemo(
    () => ({
      title,
      content,
      slug,
      meta_title: value.meta_title || title,
      meta_description: value.meta_description,
      focus_keyword: value.focus_keyword,
    }),
    [title, content, slug, value]
  );

  useEffect(() => {
    const token = getAdminToken();
    if (!token) return;
    const controller = new AbortController();
    const t = setTimeout(async () => {
      setBusy(true);
      setAnalysisError("");
      try {
        const res = await fetch(`${API_BASE}/api/admin/seo/yoast/analyze`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
          signal: controller.signal,
        });
        if (!res.ok) throw new Error(`SEO analysis failed (${res.status})`);
        setAnalysis(await res.json());
      } catch (error) {
        if (controller.signal.aborted) return;
        console.error("SEO analysis failed", error);
        setAnalysisError("SEO analysis is temporarily unavailable.");
      } finally {
        setBusy(false);
      }
    }, 400);
    return () => {
      clearTimeout(t);
      controller.abort();
    };
  }, [payload]);

  function set<K extends keyof YoastSEOValue>(key: K, v: string) {
    onChange({ ...value, [key]: v });
  }

  return (
    <div className="yoast-panel">
      <div className="yoast-header">
        <strong>Yoast SEO</strong>
        {busy && <span className="text-xs text-[var(--muted)]">Analyzing…</span>}
      </div>
      {analysisError && <p className="mb-3 text-sm text-red-500">{analysisError}</p>}

      <div className="grid sm:grid-cols-2 gap-3 mb-3">
        <div>
          <label className="field-label">Focus keyphrase</label>
          <input
            className="input"
            value={value.focus_keyword}
            onChange={(e) => set("focus_keyword", e.target.value)}
            placeholder="e.g. software engineer jobs pakistan"
          />
        </div>
        <div>
          <label className="field-label">Meta keywords</label>
          <input
            className="input"
            value={value.meta_keywords}
            onChange={(e) => set("meta_keywords", e.target.value)}
            placeholder="comma, separated, keywords"
          />
        </div>
      </div>
      <div className="mb-3">
        <label className="field-label">SEO title</label>
        <input
          className="input"
          value={value.meta_title}
          onChange={(e) => set("meta_title", e.target.value)}
          placeholder={title || "SEO title"}
          maxLength={70}
        />
      </div>
      <div className="mb-3">
        <label className="field-label">Meta description</label>
        <textarea
          className="input min-h-[80px]"
          value={value.meta_description}
          onChange={(e) => set("meta_description", e.target.value)}
          placeholder="Write a compelling meta description (120–160 chars)"
          maxLength={200}
        />
      </div>

      {analysis && (
        <>
          <div className="yoast-snippet">
            <div className="yoast-snippet-url">{analysis.snippet.url}</div>
            <div className="yoast-snippet-title">
              {value.meta_title || analysis.snippet.title}
            </div>
            <div className="yoast-snippet-desc">
              {value.meta_description || analysis.snippet.description}
            </div>
          </div>

          <div className="flex gap-4 my-3">
            <ScoreRing
              label="SEO"
              score={analysis.seo_score}
              status={analysis.seo_status}
            />
            <ScoreRing
              label="Readability"
              score={analysis.readability_score}
              status={analysis.readability_status}
            />
            <div className="text-xs text-[var(--muted)] self-center">
              {analysis.word_count} words
            </div>
          </div>

          <ul className="yoast-checks">
            {analysis.checks.map((c) => (
              <li key={c.key} className={light(c.status)}>
                <span className="yoast-dot" />
                <div>
                  <div className="font-medium text-sm">{c.label}</div>
                  <div className="text-xs text-[var(--muted)]">{c.tip}</div>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function ScoreRing({
  label,
  score,
  status,
}: {
  label: string;
  score: number;
  status: string;
}) {
  return (
    <div className={`yoast-score ${light(status)}`}>
      <div className="text-xl font-semibold tabular-nums">{Math.round(score)}</div>
      <div className="text-[10px] uppercase tracking-wider">{label}</div>
    </div>
  );
}
