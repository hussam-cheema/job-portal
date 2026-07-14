"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AdminShell } from "@/components/AdminShell";
import { RichTextEditor } from "@/components/RichTextEditor";
import { TagInput } from "@/components/TagInput";
import { YoastSEOPanel, type YoastSEOValue } from "@/components/YoastSEOPanel";
import {
  adminCreateJob,
  adminFetchQnA,
  adminUpdateJob,
  adminUpload,
  fetchFilters,
  fetchJob,
  API_BASE,
} from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import type { JobQnA } from "@/lib/types";
import { toDateInputValue } from "@/lib/format";

const empty = {
  title: "",
  description: "",
  published_date: new Date().toISOString().slice(0, 10),
  deadline_date: "",
  salary_range: "",
  source: "",
  reference_url: "",
  application_url: "",
  experience_required: "",
  education_required: "",
  skills: [] as string[],
  job_type: "private",
  cities: [] as string[],
  tags: [] as string[],
  keywords: "",
};

export default function JobFormPage() {
  const params = useParams<{ id?: string }>();
  const isNew = !params?.id || params.id === "new";
  const jobId: string | null = isNew ? null : String(params.id);
  const { token } = useAdminAuth();
  const router = useRouter();
  const [form, setForm] = useState(empty);
  const [cityOptions, setCityOptions] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qna, setQna] = useState<JobQnA[]>([]);
  const [qnaError, setQnaError] = useState<string | null>(null);
  const [qnaMessage, setQnaMessage] = useState<string | null>(null);
  const [qnaLoading, setQnaLoading] = useState(false);
  const [timer, setTimer] = useState(0);
  const [savedId, setSavedId] = useState<string | null>(jobId);
  const [attachmentCount, setAttachmentCount] = useState(0);
  const [formReady, setFormReady] = useState(isNew);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [seo, setSeo] = useState<YoastSEOValue>({
    focus_keyword: "",
    meta_title: "",
    meta_description: "",
    meta_keywords: "",
  });

  useEffect(() => {
    fetchFilters().then((f) => setCityOptions(f.cities || []));
  }, []);

  useEffect(() => {
    if (!jobId) {
      setFormReady(true);
      return;
    }
    let cancelled = false;
    setFormReady(false);
    setLoadError(null);
    fetchJob(jobId)
      .then((job) => {
        if (cancelled) return;
        if (!job) {
          setLoadError("Job not found");
          setFormReady(true);
          return;
        }
        setSavedId(job.id);
        setForm({
          title: job.title || "",
          description: job.description || "",
          published_date: toDateInputValue(job.published_date) || "",
          deadline_date: toDateInputValue(job.deadline_date || job.application_deadline) || "",
          salary_range: job.salary_range || "",
          source: job.source || job.source_name || "",
          reference_url: job.reference_url || job.source_url || "",
          application_url: job.application_url || "",
          experience_required: (job.experience_required || "").replace(/\s*year\(s\)/i, ""),
          education_required: job.education_required || "",
          skills: job.skills || [],
          job_type: job.job_type || (job.source_type === "govt" ? "government" : "private"),
          cities: job.cities?.length ? job.cities : job.city ? [job.city] : [],
          tags: (job.tags || []).filter(
            (t) => !["government", "private", "govt"].includes(t.toLowerCase())
          ),
          keywords: job.keywords || "",
        });
        setQna(job.qna || []);
        setAttachmentCount((job.attachments || []).filter((a) => !a.is_inline_image).length);
        // Load existing Yoast SEO meta if present
        fetch(`${API_BASE}/api/seo/job/${job.id}`)
          .then((r) => (r.ok ? r.json() : null))
          .then((meta) => {
            if (!meta) return;
            setSeo({
              focus_keyword: meta.focus_keyword || "",
              meta_title: meta.meta_title || "",
              meta_description: meta.meta_description || "",
              meta_keywords: meta.meta_keywords || "",
            });
          })
          .catch(() => undefined);
        setFormReady(true);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(err instanceof Error ? err.message : "Failed to load job");
        setFormReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  useEffect(() => {
    if (!qnaLoading) return;
    setTimer(0);
    const id = setInterval(() => setTimer((t) => Math.min(60, t + 1)), 1000);
    return () => clearInterval(id);
  }, [qnaLoading]);

  function setField<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    if (!form.title.trim() || !form.description.trim() || !form.published_date) {
      setError("Job title, description, and published date are required.");
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payload = {
        title: form.title.trim(),
        description: form.description,
        published_date: new Date(form.published_date).toISOString(),
        deadline_date: form.deadline_date
          ? new Date(form.deadline_date).toISOString()
          : null,
        salary_range: form.salary_range || null,
        source: form.source || null,
        reference_url: form.reference_url || null,
        application_url: form.application_url || null,
        experience_required: form.experience_required || null,
        education_required: form.education_required || null,
        skills: form.skills,
        job_type: form.job_type,
        cities: form.cities,
        tags: form.tags,
        keywords: form.keywords || null,
        seo: {
          focus_keyword: seo.focus_keyword || null,
          meta_title: seo.meta_title || null,
          meta_description: seo.meta_description || null,
          meta_keywords: seo.meta_keywords || null,
        },
      };
      const job = savedId
        ? await adminUpdateJob(token, savedId, payload)
        : await adminCreateJob(token, payload);
      setSavedId(job.id);
      setSuccess(savedId ? "Job post updated successfully." : "Job post saved successfully.");
      if (!savedId) router.push(`/admin/jobs/${job.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Job post could not be saved.");
      setSuccess(null);
    } finally {
      setSaving(false);
    }
  }

  async function onFetchQnA() {
    if (!token) return;
    if (!form.title.trim()) {
      setQnaError("Enter a job title first.");
      return;
    }
    setQnaLoading(true);
    setQnaError(null);
    setQnaMessage(null);
    try {
      if (!savedId) {
        setQnaError("Save the job before fetching YouTube Q&A.");
        return;
      }
      const result = await adminFetchQnA(token, savedId);
      setQna(result.items || []);
      if (result.error) {
        setQnaError(result.error);
      } else if (result.count > 0) {
        setQnaMessage(
          `Stored ${result.count} Q&A ${result.count === 1 ? "pair" : "pairs"} from ${result.videos_scanned} relevant ${result.videos_scanned === 1 ? "video" : "videos"}.`
        );
      } else {
        setQnaError("No relevant question-and-answer pairs were found on YouTube.");
      }
    } catch (err) {
      setQnaError(err instanceof Error ? err.message : "QnA fetch failed");
    } finally {
      setQnaLoading(false);
    }
  }

  async function uploadImage(file: File) {
    if (!token) throw new Error("Not authenticated");
    const res = await adminUpload(token, file, { jobId: savedId || undefined });
    return res.public_url.startsWith("http")
      ? res.public_url
      : `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${res.public_url}`;
  }

  async function uploadAttachment(file: File) {
    if (!token) throw new Error("Not authenticated");
    const res = await adminUpload(token, file, {
      jobId: savedId || undefined,
      asAttachment: true,
    });
    setAttachmentCount((c) => c + 1);
    const url = res.public_url.startsWith("http")
      ? res.public_url
      : `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${res.public_url}`;
    return { url, name: res.original_name || file.name };
  }

  if (!formReady) {
    return (
      <AdminShell>
        <div className="card-panel p-6 text-sm text-[var(--muted)]">Loading job…</div>
      </AdminShell>
    );
  }

  if (loadError) {
    return (
      <AdminShell>
        <div className="card-panel p-6">
          <p className="field-error">{loadError}</p>
        </div>
      </AdminShell>
    );
  }

  return (
    <AdminShell>
      <form onSubmit={onSave} className="card-panel p-5 sm:p-6 space-y-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-semibold text-[var(--navy-100)]">
            {isNew ? "Create job post" : "Edit job post"}
          </h2>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Saving…" : "Save job"}
          </button>
        </div>
        {error && <p className="field-error">{error}</p>}
        {success && <p className="text-sm text-[var(--success)] font-medium">{success}</p>}

        <div>
          <label className="field-label">Job title *</label>
          <input
            className="input"
            value={form.title}
            onChange={(e) => setField("title", e.target.value)}
            required
          />
        </div>

        <div>
          <label className="field-label">Job description *</label>
          {/* key: remount once job payload is ready (edit load) */}
          <RichTextEditor
            key={`desc-${savedId || "new"}`}
            value={form.description}
            onChange={(html) => setField("description", html)}
            placeholder="Write the full job description…"
            onUploadImage={uploadImage}
            onUploadAttachment={uploadAttachment}
            maxAttachments={3}
            attachmentCount={attachmentCount}
          />
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="field-label">Published date *</label>
            <input
              type="date"
              className="input"
              value={form.published_date}
              onChange={(e) => setField("published_date", e.target.value)}
              required
            />
          </div>
          <div>
            <label className="field-label">Deadline date</label>
            <input
              type="date"
              className="input"
              value={form.deadline_date}
              onChange={(e) => setField("deadline_date", e.target.value)}
            />
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="field-label">Expected salary range</label>
            <input
              className="input"
              value={form.salary_range}
              onChange={(e) => setField("salary_range", e.target.value)}
              placeholder="e.g. PKR 80,000 – 120,000"
            />
          </div>
          <div>
            <label className="field-label">Source</label>
            <input
              className="input"
              value={form.source}
              onChange={(e) => setField("source", e.target.value)}
              placeholder="Company / department name"
            />
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="field-label">Reference URL</label>
            <input
              type="url"
              className="input"
              value={form.reference_url}
              onChange={(e) => setField("reference_url", e.target.value)}
              placeholder="https://"
            />
          </div>
          <div>
            <label className="field-label">URL to apply</label>
            <input
              type="url"
              className="input"
              value={form.application_url}
              onChange={(e) => setField("application_url", e.target.value)}
              placeholder="https://"
            />
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="field-label">Experience required (0–100)</label>
            <div className="flex items-center gap-2">
              <input
                className="input"
                type="number"
                min={0}
                max={100}
                value={form.experience_required}
                onChange={(e) => setField("experience_required", e.target.value)}
              />
              <span className="text-sm text-[var(--muted)] whitespace-nowrap">year(s)</span>
            </div>
          </div>
          <div>
            <label className="field-label">Education required</label>
            <input
              className="input"
              value={form.education_required}
              onChange={(e) => setField("education_required", e.target.value)}
            />
          </div>
        </div>

        <div>
          <label className="field-label">Skills required</label>
          <TagInput
            values={form.skills}
            onChange={(v) => setField("skills", v)}
            placeholder="Add skill and press Enter"
          />
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="field-label">Job type</label>
            <select
              className="select"
              value={form.job_type}
              onChange={(e) => setField("job_type", e.target.value)}
            >
              <option value="government">Government Job</option>
              <option value="private">Private Job</option>
            </select>
          </div>
          <div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label className="field-label mb-0">City / Cities</label>
              {cityOptions.length > 0 && (
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="text-xs font-medium text-[var(--accent)] underline underline-offset-4"
                    onClick={() => setField("cities", cityOptions)}
                  >
                    Select all cities
                  </button>
                  {form.cities.length > 0 && (
                    <button
                      type="button"
                      className="text-xs text-[var(--muted)] underline underline-offset-4"
                      onClick={() => setField("cities", [])}
                    >
                      Clear
                    </button>
                  )}
                </div>
              )}
            </div>
            <TagInput
              values={form.cities}
              onChange={(v) => setField("cities", v)}
              placeholder="Add city and press Enter"
            />
            {cityOptions.length > 0 && (
              <select
                className="select mt-2"
                value=""
                onChange={(e) => {
                  if (e.target.value) {
                    setField(
                      "cities",
                      form.cities.includes(e.target.value)
                        ? form.cities
                        : [...form.cities, e.target.value]
                    );
                  }
                }}
              >
                <option value="">Add from list…</option>
                {cityOptions.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        <div>
          <label className="field-label">Tags (categories)</label>
          <TagInput
            values={form.tags}
            onChange={(v) => setField("tags", v)}
            placeholder="Add tag and press Enter"
          />
        </div>

        <div>
          <label className="field-label">Keywords</label>
          <RichTextEditor
            key={`kw-${savedId || "new"}`}
            value={form.keywords}
            onChange={(html) => setField("keywords", html)}
            placeholder="SEO / search keywords…"
            onUploadImage={uploadImage}
          />
        </div>

        <YoastSEOPanel
          title={form.title}
          content={form.description}
          slug={savedId || undefined}
          value={seo}
          onChange={setSeo}
        />

        <div className="border-t border-[var(--border)] pt-5">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="btn btn-primary"
              onClick={onFetchQnA}
              disabled={qnaLoading || !savedId}
            >
              {qnaLoading
                ? `Fetching QnA… ${timer}s`
                : "Replace Q&A from YouTube"}
            </button>
            {qnaLoading && (
              <span className="text-sm text-[var(--muted)] font-mono">
                Timer: {timer}s {timer >= 60 ? "(stopping at 60s)" : ""}
              </span>
            )}
          </div>
          {qnaError && <p className="field-error mt-2">{qnaError}</p>}
          {qnaMessage && <p className="mt-2 text-sm font-medium text-[var(--success)]">{qnaMessage}</p>}
          {qna.length > 0 && (
            <ol className="mt-4 space-y-3 list-decimal list-inside">
              {qna.map((item, idx) => (
                <li
                  key={item.id || idx}
                  className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-3 text-sm"
                >
                  <div className="font-medium text-[var(--navy-100)]">Q: {item.question}</div>
                  <div className="text-[var(--navy-200)] mt-1">A: {item.answer}</div>
                  {item.youtube_url && (
                    <a
                      href={item.youtube_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-[var(--accent)] hover:underline mt-1 inline-block"
                    >
                      {item.youtube_title || item.youtube_url}
                    </a>
                  )}
                </li>
              ))}
            </ol>
          )}
          {!qnaLoading && qna.length === 0 && !qnaError && (
            <p className="mt-2 text-sm text-[var(--muted)]">
              {savedId ? "No Q&A stored for this job." : "Save the job to fetch YouTube Q&A."}
            </p>
          )}
        </div>
      </form>
    </AdminShell>
  );
}
