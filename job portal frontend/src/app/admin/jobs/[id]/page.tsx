"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AdminShell } from "@/components/AdminShell";
import { EditorDraftStatus } from "@/components/EditorDraftStatus";
import { RichTextEditor } from "@/components/RichTextEditor";
import { TagInput } from "@/components/TagInput";
import { YoastSEOPanel, type YoastSEOValue } from "@/components/YoastSEOPanel";
import {
  adminCreateJob,
  adminFetchQnA,
  adminListTaxonomy,
  adminUpdateJob,
  adminUpload,
  fetchFilters,
  fetchJob,
  API_BASE,
} from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import {
  cloneDraftData,
  deleteEditorDraft,
  readEditorDraft,
  saveEditorDraft,
} from "@/lib/editorDrafts";
import type { JobQnA, QnAMatchedVideo, TaxonomyTerm } from "@/lib/types";
import { dateInputToApiValue, toDateInputValue, todayInPakistan } from "@/lib/format";

const empty = {
  title: "",
  description: "",
  published_date: todayInPakistan(),
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
  provinces: [] as string[],
  tags: [] as string[],
  keywords: "",
};

const emptySeo: YoastSEOValue = {
  focus_keyword: "",
  meta_title: "",
  meta_description: "",
  meta_keywords: "",
};

type JobEditorSnapshot = {
  form: typeof empty;
  seo: YoastSEOValue;
  attachmentCount: number;
};

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asStringList(value: unknown): string[] {
  let candidates: unknown[] = [];
  if (Array.isArray(value)) {
    candidates = value;
  } else if (typeof value === "string" && value.trim()) {
    try {
      const parsed: unknown = JSON.parse(value);
      candidates = Array.isArray(parsed) ? parsed : value.split(",");
    } catch {
      candidates = value.split(",");
    }
  }

  const result: string[] = [];
  const seen = new Set<string>();
  for (const candidate of candidates) {
    if (typeof candidate !== "string") continue;
    const clean = candidate.trim();
    const key = clean.toLocaleLowerCase();
    if (!clean || seen.has(key)) continue;
    seen.add(key);
    result.push(clean);
  }
  return result;
}

function emptyJobSnapshot(): JobEditorSnapshot {
  return {
    form: {
      ...empty,
      skills: [],
      cities: [],
      provinces: [],
      tags: [],
    },
    seo: { ...emptySeo },
    attachmentCount: 0,
  };
}

function normalizeJobDraft(
  value: unknown,
  fallback: JobEditorSnapshot
): JobEditorSnapshot {
  if (!value || typeof value !== "object") return cloneDraftData(fallback);
  const candidate = value as Partial<JobEditorSnapshot>;
  const candidateForm =
    candidate.form && typeof candidate.form === "object"
      ? (candidate.form as Partial<typeof empty>)
      : {};
  const candidateSeo =
    candidate.seo && typeof candidate.seo === "object"
      ? (candidate.seo as Partial<YoastSEOValue>)
      : {};
  return {
    form: {
      ...fallback.form,
      ...candidateForm,
      skills: asStringList(candidateForm.skills ?? fallback.form.skills),
      cities: asStringList(candidateForm.cities ?? fallback.form.cities),
      provinces: asStringList(candidateForm.provinces ?? fallback.form.provinces),
      tags: asStringList(candidateForm.tags ?? fallback.form.tags),
    },
    seo: {
      ...fallback.seo,
      ...candidateSeo,
    },
    attachmentCount:
      typeof candidate.attachmentCount === "number" &&
      Number.isFinite(candidate.attachmentCount)
        ? Math.max(0, candidate.attachmentCount)
        : fallback.attachmentCount,
  };
}

function hasMeaningfulJobDraft(snapshot: JobEditorSnapshot) {
  const { form, seo } = snapshot;
  const richText = `${form.description} ${form.keywords}`
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .trim();
  return Boolean(
    form.title.trim() ||
      richText ||
      form.deadline_date ||
      form.salary_range.trim() ||
      form.source.trim() ||
      form.reference_url.trim() ||
      form.application_url.trim() ||
      form.experience_required.trim() ||
      form.education_required.trim() ||
      form.skills.length ||
      form.cities.length ||
      form.provinces.length ||
      form.tags.length ||
      Object.values(seo).some((value) => value.trim())
  );
}

function optionalWholeNumber(
  value: string,
  label: string,
  minimum: number,
  maximum: number
): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < minimum || parsed > maximum) {
    throw new Error(`${label} must be a whole number from ${minimum} to ${maximum}.`);
  }
  return parsed;
}

export default function JobFormPage() {
  const params = useParams<{ id?: string }>();
  const router = useRouter();
  const isNew = !params?.id || params.id === "new";
  const jobId: string | null = isNew ? null : String(params.id);
  const { token } = useAdminAuth();
  const [form, setForm] = useState(empty);
  const [cityOptions, setCityOptions] = useState<string[]>([]);
  const [provinceOptions, setProvinceOptions] = useState<string[]>([]);
  const [categoryOptions, setCategoryOptions] = useState<TaxonomyTerm[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [qna, setQna] = useState<JobQnA[]>([]);
  const [qnaError, setQnaError] = useState<string | null>(null);
  const [qnaMessage, setQnaMessage] = useState<string | null>(null);
  const [qnaPipeline, setQnaPipeline] = useState<{
    videosCompared: number;
    matchedVideos: QnAMatchedVideo[];
  } | null>(null);
  const [qnaLoading, setQnaLoading] = useState(false);
  const [qnaSimilarityPercent, setQnaSimilarityPercent] = useState("");
  const [qnaVideoCount, setQnaVideoCount] = useState("");
  const [qnaCommentCount, setQnaCommentCount] = useState("");
  const [savedId, setSavedId] = useState<string | null>(jobId);
  const [attachmentCount, setAttachmentCount] = useState(0);
  const [formReady, setFormReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [seo, setSeo] = useState<YoastSEOValue>(emptySeo);
  const [draftReady, setDraftReady] = useState(false);
  const [draftRecovered, setDraftRecovered] = useState(false);
  const [draftUpdatedAt, setDraftUpdatedAt] = useState<string | null>(null);
  const [draftStorageError, setDraftStorageError] = useState<string | null>(null);
  const draftRecordId = jobId || "new";
  const baselineDataRef = useRef<JobEditorSnapshot>(emptyJobSnapshot());
  const baselineSerializedRef = useRef(JSON.stringify(baselineDataRef.current));

  const editorSnapshot = useMemo<JobEditorSnapshot>(
    () => ({ form, seo, attachmentCount }),
    [attachmentCount, form, seo]
  );

  useEffect(() => {
    fetchFilters().then((f) => {
      setCityOptions(asStringList(f.cities));
      setProvinceOptions(asStringList(f.provinces));
    });
    if (token) {
      adminListTaxonomy(token).then(setCategoryOptions).catch(() => setCategoryOptions([]));
    }
  }, [token]);

  useEffect(() => {
    let cancelled = false;
    setFormReady(false);
    setDraftReady(false);
    setLoadError(null);

    async function hydrateEditor() {
      let baseline = emptyJobSnapshot();
      if (jobId) {
        const job = await fetchJob(jobId);
        if (!job) throw new Error("Job not found");
        const skills = asStringList(job.skills);
        const cities = asStringList(job.cities);
        const provinces = asStringList(job.provinces);
        const tags = asStringList(job.tags);
        const serverForm = {
          ...empty,
          title: asString(job.title),
          description: asString(job.description),
          published_date: toDateInputValue(job.published_date) || "",
          deadline_date:
            toDateInputValue(job.deadline_date || job.application_deadline) || "",
          salary_range: asString(job.salary_range),
          source: asString(job.source || job.source_name),
          reference_url: asString(job.reference_url || job.source_url),
          application_url: asString(job.application_url),
          experience_required: asString(job.experience_required).replace(
            /\s*year\(s\)/i,
            ""
          ),
          education_required: asString(job.education_required),
          skills,
          job_type:
            asString(job.job_type) ||
            (job.source_type === "govt" ? "government" : "private"),
          cities: cities.length ? cities : asStringList(job.city),
          provinces: provinces.length ? provinces : asStringList(job.province),
          tags: tags.filter(
            (tag) => !["government", "private", "govt"].includes(tag.toLowerCase())
          ),
          keywords: asString(job.keywords),
        };
        const serverAttachmentCount = (
          Array.isArray(job.attachments) ? job.attachments : []
        ).filter(
          (attachment) => attachment && !attachment.is_inline_image
        ).length;
        let serverSeo = { ...emptySeo };
        try {
          const response = await fetch(`${API_BASE}/api/seo/job/${job.id}`, {
            cache: "no-store",
          });
          const meta = response.ok ? await response.json() : null;
          if (meta) {
            serverSeo = {
              focus_keyword: meta.focus_keyword || "",
              meta_title: meta.meta_title || "",
              meta_description: meta.meta_description || "",
              meta_keywords: meta.meta_keywords || "",
            };
          }
        } catch {
          // SEO is optional; the post and any local draft still remain editable.
        }
        baseline = {
          form: serverForm,
          seo: serverSeo,
          attachmentCount: serverAttachmentCount,
        };
        if (cancelled) return;
        setSavedId(asString(job.id));
        setQna(Array.isArray(job.qna) ? job.qna : []);
      }

      if (cancelled) return;
      baselineDataRef.current = cloneDraftData(baseline);
      baselineSerializedRef.current = JSON.stringify(baseline);
      const localDraft = readEditorDraft<JobEditorSnapshot>("job", draftRecordId);
      const initial = localDraft
        ? normalizeJobDraft(localDraft.data, baseline)
        : cloneDraftData(baseline);

      setForm(initial.form);
      setSeo(initial.seo);
      setAttachmentCount(initial.attachmentCount);
      setDraftRecovered(Boolean(localDraft));
      setDraftUpdatedAt(localDraft?.updatedAt || null);
      setDraftStorageError(null);
      setDraftReady(true);
      setFormReady(true);
    }

    hydrateEditor().catch((err) => {
      if (cancelled) return;
      setLoadError(err instanceof Error ? err.message : "Failed to load job");
      setDraftReady(true);
      setFormReady(true);
    });

    return () => {
      cancelled = true;
    };
  }, [draftRecordId, jobId]);

  useEffect(() => {
    if (!draftReady || !formReady || saving) return;
    const serialized = JSON.stringify(editorSnapshot);
    const unchanged = serialized === baselineSerializedRef.current;
    const meaningful = hasMeaningfulJobDraft(editorSnapshot);

    if (unchanged || !meaningful) {
      deleteEditorDraft("job", draftRecordId);
      setDraftRecovered(false);
      setDraftUpdatedAt(null);
      setDraftStorageError(null);
      return;
    }

    const timerId = window.setTimeout(() => {
      const savedDraft = saveEditorDraft({
        kind: "job",
        recordId: draftRecordId,
        title: form.title || "Untitled job post",
        data: editorSnapshot,
      });
      if (!savedDraft) {
        setDraftStorageError(
          "Browser storage is unavailable or full. Copy your content before leaving this page."
        );
        return;
      }
      setDraftStorageError(null);
      setDraftUpdatedAt(savedDraft.updatedAt);
    }, 500);
    return () => window.clearTimeout(timerId);
  }, [draftReady, draftRecordId, editorSnapshot, form.title, formReady, saving]);

  useEffect(() => {
    if (!draftReady || !formReady) return;
    const persistImmediately = () => {
      const serialized = JSON.stringify(editorSnapshot);
      if (
        serialized === baselineSerializedRef.current ||
        !hasMeaningfulJobDraft(editorSnapshot)
      ) {
        return;
      }
      saveEditorDraft({
        kind: "job",
        recordId: draftRecordId,
        title: form.title || "Untitled job post",
        data: editorSnapshot,
      });
    };
    const persistBeforeLinkNavigation = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const link = target.closest<HTMLAnchorElement>("a[href]");
      if (!link) return;
      const destination = new URL(link.href, window.location.href);
      if (destination.origin === window.location.origin) persistImmediately();
    };
    window.addEventListener("pagehide", persistImmediately);
    window.addEventListener("beforeunload", persistImmediately);
    document.addEventListener("click", persistBeforeLinkNavigation, true);
    return () => {
      window.removeEventListener("pagehide", persistImmediately);
      window.removeEventListener("beforeunload", persistImmediately);
      document.removeEventListener("click", persistBeforeLinkNavigation, true);
    };
  }, [draftReady, draftRecordId, editorSnapshot, form.title, formReady]);

  function discardDraft() {
    deleteEditorDraft("job", draftRecordId);
    const baseline = cloneDraftData(baselineDataRef.current);
    setForm(baseline.form);
    setSeo(baseline.seo);
    setAttachmentCount(baseline.attachmentCount);
    setDraftRecovered(false);
    setDraftUpdatedAt(null);
    setDraftStorageError(null);
    setError(null);
    setSuccess(null);
  }

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
        published_date: dateInputToApiValue(form.published_date) || "",
        deadline_date: dateInputToApiValue(form.deadline_date),
        salary_range: form.salary_range || null,
        source: form.source || null,
        reference_url: form.reference_url || null,
        application_url: form.application_url || null,
        experience_required: form.experience_required || null,
        education_required: form.education_required || null,
        skills: form.skills,
        job_type: form.job_type,
        cities: form.cities,
        provinces: form.provinces,
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
      const savedSnapshot = cloneDraftData(editorSnapshot);
      baselineDataRef.current = savedSnapshot;
      baselineSerializedRef.current = JSON.stringify(savedSnapshot);
      deleteEditorDraft("job", draftRecordId);
      setDraftRecovered(false);
      setDraftUpdatedAt(null);
      setDraftStorageError(null);
      setSavedId(job.id);
      setSuccess(savedId ? "Job post updated successfully." : "Job post saved successfully.");
      if (!savedId) router.replace(`/admin/jobs/${job.id}`);
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
    setQnaPipeline(null);
    try {
      if (!savedId) {
        setQnaError("Save the job before fetching YouTube Q&A.");
        return;
      }
      const result = await adminFetchQnA(token, savedId, {
        min_similarity_percent: optionalWholeNumber(
          qnaSimilarityPercent,
          "Cosine similarity percentage",
          1,
          100
        ),
        max_youtube_videos: optionalWholeNumber(
          qnaVideoCount,
          "YouTube video count",
          1,
          50
        ),
        max_comments: optionalWholeNumber(
          qnaCommentCount,
          "Comment count",
          1,
          500
        ),
      });
      setQna(result.items || []);
      setQnaPipeline({
        videosCompared: result.videos_compared || 0,
        matchedVideos: result.matched_videos || [],
      });
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
        <EditorDraftStatus
          updatedAt={draftUpdatedAt}
          recovered={draftRecovered}
          storageError={draftStorageError}
          onDiscard={discardDraft}
        />

        <div>
          <label className="field-label">Job title *</label>
          <input
            className="input"
            aria-label="Job title"
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
            <label className="field-label">Job Advertisement Reference URL</label>
            <input
              type="url"
              className="input"
              value={form.reference_url}
              onChange={(e) => setField("reference_url", e.target.value)}
              placeholder="https://"
            />
          </div>
          <div>
            <label className="field-label">Apply Here</label>
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
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="field-label mb-0">Province / Territory</label>
            {form.provinces.length > 0 && (
              <button
                type="button"
                className="text-xs text-[var(--muted)] underline underline-offset-4"
                onClick={() => setField("provinces", [])}
              >
                Clear
              </button>
            )}
          </div>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Select a whole province or territory when the vacancy is not limited to individual cities.
          </p>
          {form.provinces.length > 0 && (
            <div className="my-2 flex flex-wrap gap-2 rounded-xl border border-[var(--border)] p-3">
              {form.provinces.map((province) => (
                <span key={province} className="tag flex items-center gap-1.5">
                  {province}
                  <button
                    type="button"
                    aria-label={`Remove ${province}`}
                    className="font-bold text-[var(--muted)] hover:text-red-500"
                    onClick={() =>
                      setField(
                        "provinces",
                        form.provinces.filter((value) => value !== province)
                      )
                    }
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          <select
            className="select mt-2"
            aria-label="Add province or territory"
            value=""
            onChange={(event) => {
              const selected = event.target.value;
              if (selected && !form.provinces.includes(selected)) {
                setField("provinces", [...form.provinces, selected]);
              }
            }}
          >
            <option value="">Add province or territory…</option>
            {provinceOptions
              .filter((province) => !form.provinces.includes(province))
              .map((province) => (
                <option key={province} value={province}>
                  {province}
                </option>
              ))}
          </select>
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
            {form.cities.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-2 rounded-xl border border-[var(--border)] p-3">
                {form.cities.map((city) => (
                  <span key={city} className="tag flex items-center gap-1.5">
                    {city}
                    <button
                      type="button"
                      aria-label={`Remove ${city}`}
                      className="font-bold text-[var(--muted)] hover:text-red-500"
                      onClick={() => setField("cities", form.cities.filter((value) => value !== city))}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
            {cityOptions.length > 0 && (
              <select
                className="select mt-2"
                aria-label="Add city from predefined list"
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
          {form.tags.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2 rounded-xl border border-[var(--border)] p-3">
              {form.tags.map((tag) => (
                <span key={tag} className="tag flex items-center gap-1.5">
                  {tag}
                  <button
                    type="button"
                    aria-label={`Remove category ${tag}`}
                    className="font-bold text-[var(--muted)] hover:text-red-500"
                    onClick={() => setField("tags", form.tags.filter((value) => value.toLowerCase() !== tag.toLowerCase()))}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          <select
            className="select"
            aria-label="Select tags or categories"
            value=""
            onChange={(event) => {
              const selected = event.target.value;
              if (!selected || form.tags.some((value) => value.toLowerCase() === selected.toLowerCase())) return;
              setField("tags", [...form.tags, selected]);
            }}
          >
            <option value="">Select one or more categories…</option>
            {categoryOptions
              .filter((term) => term.is_active)
              .filter((term) => !form.tags.some((value) => value.toLowerCase() === term.name.toLowerCase()))
              .map((term) => (
                <option key={term.id} value={term.name}>{term.name}</option>
              ))}
          </select>
          {form.tags.length > 0 && categoryOptions.some((term) => !term.is_active && form.tags.some((value) => value.toLowerCase() === term.name.toLowerCase())) && (
            <p className="mt-2 text-xs text-[var(--muted)]">Inactive categories already assigned to this post remain selected until removed.</p>
          )}
          {categoryOptions.length === 0 && <p className="mt-2 text-sm text-[var(--muted)]">Create tags/categories from the dashboard first.</p>}
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

        <section className="rounded-3xl border border-[var(--border)] bg-[var(--navy-900)] px-5 py-7 shadow-sm sm:px-8 sm:py-9">
          <div className="mx-auto max-w-4xl">
            <div className="text-center">
              <h3 className="text-xl font-semibold text-[var(--navy-100)] sm:text-2xl">
                Search Q&A from YouTube
              </h3>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Leave any field empty to use its default value.
              </p>
            </div>

            <div className="mx-auto mt-7 grid max-w-3xl gap-5 sm:mt-9 sm:gap-6">
              <label className="grid gap-2 sm:grid-cols-[minmax(190px,0.75fr)_minmax(0,1.4fr)] sm:items-start sm:gap-6">
                <span className="field-label mb-0 sm:pt-3">Matching percentage</span>
                <input
                  className="input"
                  type="number"
                  min={1}
                  max={100}
                  step={1}
                  inputMode="numeric"
                  aria-label="Cosine similarity percentage"
                  placeholder="Set matching percentage (default: 80%)"
                  value={qnaSimilarityPercent}
                  onChange={(event) => setQnaSimilarityPercent(event.target.value)}
                />
              </label>
              <label className="grid gap-2 sm:grid-cols-[minmax(190px,0.75fr)_minmax(0,1.4fr)] sm:items-start sm:gap-6">
                <span className="field-label mb-0 sm:pt-3">YouTube videos</span>
                <input
                  className="input"
                  type="number"
                  min={1}
                  max={50}
                  step={1}
                  inputMode="numeric"
                  aria-label="YouTube videos to compare"
                  placeholder="Set number of videos (default: 5)"
                  value={qnaVideoCount}
                  onChange={(event) => setQnaVideoCount(event.target.value)}
                />
              </label>
              <label className="grid gap-2 sm:grid-cols-[minmax(190px,0.75fr)_minmax(0,1.4fr)] sm:items-start sm:gap-6">
                <span className="field-label mb-0 sm:pt-3">Comments per video</span>
                <span className="block">
                  <input
                    className="input"
                    type="number"
                    min={1}
                    max={500}
                    step={1}
                    inputMode="numeric"
                    aria-label="Comments per video"
                    placeholder="Set comments per video (default: 50)"
                    value={qnaCommentCount}
                    onChange={(event) => setQnaCommentCount(event.target.value)}
                  />
                  <span className="mt-2 block text-xs text-[var(--muted)]">
                    Every nested reply under each selected comment is included.
                  </span>
                </span>
              </label>
            </div>

            <div className="mt-8 flex justify-center sm:mt-10">
              <button
                type="button"
                className="btn btn-primary w-full justify-center sm:w-auto sm:min-w-72"
                onClick={onFetchQnA}
                disabled={qnaLoading || !savedId}
              >
                {qnaLoading ? "Fetching Q&A…" : "Replace Q&A from YouTube"}
              </button>
            </div>
          </div>
          {qnaError && <p className="field-error mt-2">{qnaError}</p>}
          {qnaMessage && <p className="mt-2 text-sm font-medium text-[var(--success)]">{qnaMessage}</p>}
          {qnaPipeline && qnaPipeline.videosCompared > 0 && (
            <div className="mt-4 rounded-2xl border border-[var(--border)] bg-[var(--navy-850)] p-4 text-sm">
              <p className="font-medium text-[var(--navy-100)]">
                Compared {qnaPipeline.videosCompared} newest YouTube video
                {qnaPipeline.videosCompared === 1 ? "" : "s"}; {qnaPipeline.matchedVideos.length}{" "}
                met the raw cosine threshold.
              </p>
              {qnaPipeline.matchedVideos.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {qnaPipeline.matchedVideos.map((video) => (
                    <li key={video.url} className="text-[var(--muted)]">
                      <a
                        href={video.url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-[var(--accent)] hover:underline"
                      >
                        {video.title}
                      </a>
                      {` — ${video.similarity_percent.toFixed(1)}% cosine; `}
                      {video.has_transcript ? "transcript available" : "no transcript"}
                      {`; ${video.comment_threads} comment ${
                        video.comment_threads === 1 ? "thread" : "threads"
                      }`}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
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
        </section>
      </form>
    </AdminShell>
  );
}
