"use client";

import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useParams, useRouter } from "next/navigation";
import { AdminRouteLink } from "@/components/AdminRouteLink";
import { AdminShell } from "@/components/AdminShell";
import { EditorDraftStatus } from "@/components/EditorDraftStatus";
import { RichTextEditor } from "@/components/RichTextEditor";
import { TagInput } from "@/components/TagInput";
import { YoastSEOPanel, type YoastSEOValue } from "@/components/YoastSEOPanel";
import { API_BASE, adminGetBlogPost, adminSaveBlogPost, adminUpload } from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import {
  cloneDraftData,
  deleteEditorDraft,
  readEditorDraft,
  saveEditorDraft,
} from "@/lib/editorDrafts";

const emptyBlogForm = {
  title: "",
  slug: "",
  excerpt: "",
  content: "",
  author: "",
  category: "",
  tags: [] as string[],
  is_published: false,
  published_at: "",
};

const emptySeo: YoastSEOValue = {
  focus_keyword: "",
  meta_title: "",
  meta_description: "",
  meta_keywords: "",
};

type BlogEditorSnapshot = {
  form: typeof emptyBlogForm;
  seo: YoastSEOValue;
  slugTouched: boolean;
};

function slugify(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9\s-]/g, "").replace(/\s+/g, "-").replace(/-+/g, "-").slice(0, 120);
}

function toDateTimeInput(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16);
}

function emptyBlogSnapshot(): BlogEditorSnapshot {
  return {
    form: { ...emptyBlogForm, tags: [] },
    seo: { ...emptySeo },
    slugTouched: false,
  };
}

function normalizeBlogDraft(
  value: unknown,
  fallback: BlogEditorSnapshot
): BlogEditorSnapshot {
  if (!value || typeof value !== "object") return cloneDraftData(fallback);
  const candidate = value as Partial<BlogEditorSnapshot>;
  const candidateForm =
    candidate.form && typeof candidate.form === "object"
      ? (candidate.form as Partial<typeof emptyBlogForm>)
      : {};
  const candidateSeo =
    candidate.seo && typeof candidate.seo === "object"
      ? (candidate.seo as Partial<YoastSEOValue>)
      : {};
  return {
    form: {
      ...fallback.form,
      ...candidateForm,
      tags: Array.isArray(candidateForm.tags)
        ? candidateForm.tags.filter((tag): tag is string => typeof tag === "string")
        : fallback.form.tags,
    },
    seo: { ...fallback.seo, ...candidateSeo },
    slugTouched:
      typeof candidate.slugTouched === "boolean"
        ? candidate.slugTouched
        : fallback.slugTouched,
  };
}

function hasMeaningfulBlogDraft(snapshot: BlogEditorSnapshot) {
  const { form, seo } = snapshot;
  const richText = form.content
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .trim();
  return Boolean(
    form.title.trim() ||
      form.excerpt.trim() ||
      richText ||
      form.author.trim() ||
      form.category.trim() ||
      form.tags.length ||
      form.published_at ||
      form.is_published ||
      Object.values(seo).some((value) => value.trim())
  );
}

export default function AdminBlogFormPage() {
  const params = useParams<{ id?: string }>();
  const router = useRouter();
  const isNew = !params?.id || params.id === "new";
  const postId = isNew ? null : String(params.id);
  const { token, ready } = useAdminAuth();
  const [form, setForm] = useState(emptyBlogForm);
  const [seo, setSeo] = useState<YoastSEOValue>(emptySeo);
  const [slugTouched, setSlugTouched] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [draftReady, setDraftReady] = useState(false);
  const [draftRecovered, setDraftRecovered] = useState(false);
  const [draftUpdatedAt, setDraftUpdatedAt] = useState<string | null>(null);
  const [draftStorageError, setDraftStorageError] = useState<string | null>(null);
  const draftRecordId = postId || "new";
  const baselineDataRef = useRef<BlogEditorSnapshot>(emptyBlogSnapshot());
  const baselineSerializedRef = useRef(JSON.stringify(baselineDataRef.current));

  const editorSnapshot = useMemo<BlogEditorSnapshot>(
    () => ({ form, seo, slugTouched }),
    [form, seo, slugTouched]
  );

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    setLoading(true);
    setDraftReady(false);
    setError("");

    async function hydrateEditor() {
      try {
        let baseline = emptyBlogSnapshot();
        if (postId && token) {
          const post = await adminGetBlogPost(token, postId);
          let serverSeo = { ...emptySeo };
          try {
            const response = await fetch(`${API_BASE}/api/seo/blog/${postId}`, {
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
            // SEO is optional; the post and any local draft remain editable.
          }
          baseline = {
            form: {
              title: post.title,
              slug: post.slug,
              excerpt: post.excerpt || "",
              content: post.content,
              author: post.author || "",
              category: post.category || "",
              tags: post.tags || [],
              is_published: post.is_published,
              published_at: toDateTimeInput(post.published_at),
            },
            seo: serverSeo,
            slugTouched: true,
          };
        }

        if (cancelled) return;
        baselineDataRef.current = cloneDraftData(baseline);
        baselineSerializedRef.current = JSON.stringify(baseline);
        const localDraft = readEditorDraft<BlogEditorSnapshot>(
          "blog",
          draftRecordId
        );
        const initial = localDraft
          ? normalizeBlogDraft(localDraft.data, baseline)
          : cloneDraftData(baseline);
        setForm(initial.form);
        setSeo(initial.seo);
        setSlugTouched(initial.slugTouched);
        setDraftRecovered(Boolean(localDraft));
        setDraftUpdatedAt(localDraft?.updatedAt || null);
        setDraftStorageError(null);
        setDraftReady(true);
        setLoading(false);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load blog post");
          setDraftReady(true);
          setLoading(false);
        }
      }
    }
    void hydrateEditor();
    return () => {
      cancelled = true;
    };
  }, [draftRecordId, postId, ready, token]);

  useEffect(() => {
    if (!draftReady || loading || saving) return;
    const serialized = JSON.stringify(editorSnapshot);
    const unchanged = serialized === baselineSerializedRef.current;
    const meaningful = hasMeaningfulBlogDraft(editorSnapshot);

    if (unchanged || !meaningful) {
      deleteEditorDraft("blog", draftRecordId);
      setDraftRecovered(false);
      setDraftUpdatedAt(null);
      setDraftStorageError(null);
      return;
    }

    const timerId = window.setTimeout(() => {
      const savedDraft = saveEditorDraft({
        kind: "blog",
        recordId: draftRecordId,
        title: form.title || "Untitled blog post",
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
  }, [draftReady, draftRecordId, editorSnapshot, form.title, loading, saving]);

  useEffect(() => {
    if (!draftReady || loading) return;
    const persistImmediately = () => {
      const serialized = JSON.stringify(editorSnapshot);
      if (
        serialized === baselineSerializedRef.current ||
        !hasMeaningfulBlogDraft(editorSnapshot)
      ) {
        return;
      }
      saveEditorDraft({
        kind: "blog",
        recordId: draftRecordId,
        title: form.title || "Untitled blog post",
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
  }, [draftReady, draftRecordId, editorSnapshot, form.title, loading]);

  function discardDraft() {
    deleteEditorDraft("blog", draftRecordId);
    const baseline = cloneDraftData(baselineDataRef.current);
    setForm(baseline.form);
    setSeo(baseline.seo);
    setSlugTouched(baseline.slugTouched);
    setDraftRecovered(false);
    setDraftUpdatedAt(null);
    setDraftStorageError(null);
    setError("");
    setSuccess("");
  }

  const uploadImage = useCallback(async (file: File) => {
    if (!token) throw new Error("Your admin session expired. Please sign in again.");
    const uploaded = await adminUpload(token, file);
    return uploaded.public_url;
  }, [token]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!token || !form.title.trim() || !form.slug.trim()) { setError("Title and slug are required."); return; }
    setSaving(true); setError(""); setSuccess("");
    try {
      const saved = await adminSaveBlogPost(token, postId, {
        title: form.title.trim(), slug: form.slug.trim(), excerpt: form.excerpt.trim() || null,
        content: form.content, author: form.author.trim() || null, category: form.category.trim() || null,
        tags: form.tags, is_published: form.is_published,
        published_at: form.published_at ? new Date(form.published_at).toISOString() : null,
        seo: { focus_keyword: seo.focus_keyword || null, meta_title: seo.meta_title || null, meta_description: seo.meta_description || null, meta_keywords: seo.meta_keywords || null },
      });
      const savedSnapshot = cloneDraftData(editorSnapshot);
      baselineDataRef.current = savedSnapshot;
      baselineSerializedRef.current = JSON.stringify(savedSnapshot);
      deleteEditorDraft("blog", draftRecordId);
      setDraftRecovered(false);
      setDraftUpdatedAt(null);
      setDraftStorageError(null);
      setSuccess(isNew ? "Blog post created successfully." : "Blog post updated successfully.");
      if (isNew) router.replace(`/admin/blog/${saved.id}`);
    } catch (e) { setError(e instanceof Error ? e.message : "Blog post could not be saved."); }
    finally { setSaving(false); }
  }

  if (loading) return <AdminShell><div className="card-panel p-6 text-sm text-[var(--muted)]">Loading blog editor…</div></AdminShell>;

  return <AdminShell>
    <form onSubmit={save} className="card-panel space-y-5 p-4 sm:p-6">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div><h2 className="text-xl font-semibold text-[var(--navy-100)]">{isNew ? "Create blog post" : "Edit blog post"}</h2><p className="text-xs text-[var(--muted)]">Rich content editor with Yoast SEO analysis</p></div>
        <div className="flex gap-2"><AdminRouteLink href="/admin/blog" className="btn btn-ghost">← All posts</AdminRouteLink><button className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : "Save post"}</button></div>
      </div>
      {error && <p className="field-error">{error}</p>}{success && <p className="text-sm font-medium text-[var(--success)]">{success}</p>}
      <EditorDraftStatus
        updatedAt={draftUpdatedAt}
        recovered={draftRecovered}
        storageError={draftStorageError}
        onDiscard={discardDraft}
      />
      <div><label className="field-label">Title *</label><input className="input" aria-label="Blog title" value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value, slug: slugTouched ? p.slug : slugify(e.target.value) }))} required /></div>
      <div><label className="field-label">Slug *</label><div className="flex items-center gap-2"><span className="text-sm text-[var(--muted)]">/blog/</span><input className="input" aria-label="Blog slug" value={form.slug} onChange={(e) => { setSlugTouched(true); setForm((p) => ({ ...p, slug: slugify(e.target.value) })); }} required /></div></div>
      <div><label className="field-label">Excerpt</label><textarea className="input min-h-24" value={form.excerpt} onChange={(e) => setForm({ ...form, excerpt: e.target.value })} maxLength={600} placeholder="A concise summary shown in the blog listing" /></div>
      <div className="grid gap-4 sm:grid-cols-2"><div><label className="field-label">Author</label><input className="input" value={form.author} onChange={(e) => setForm({ ...form, author: e.target.value })} /></div><div><label className="field-label">Category</label><input className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="Career Advice" /></div></div>
      <div><label className="field-label">Tags</label><TagInput values={form.tags} onChange={(tags) => setForm({ ...form, tags })} placeholder="Type a tag and press Enter" /></div>
      <div><label className="field-label">Article content</label><RichTextEditor key={`blog-${postId || "new"}`} value={form.content} onChange={(content) => setForm((previous) => ({ ...previous, content }))} onUploadImage={uploadImage} placeholder="Write the blog post…" /></div>
      <div className="grid gap-4 sm:grid-cols-2"><label className="flex items-center gap-2 text-sm text-[var(--navy-200)]"><input type="checkbox" checked={form.is_published} onChange={(e) => setForm({ ...form, is_published: e.target.checked })} /> Published</label><div><label className="field-label">Publish date and time</label><input type="datetime-local" className="input" value={form.published_at} onChange={(e) => setForm({ ...form, published_at: e.target.value })} /></div></div>
      <YoastSEOPanel title={form.title} content={form.content} slug={`blog/${form.slug}`} value={seo} onChange={setSeo} />
      <div className="flex gap-2 border-t border-[var(--border)] pt-5"><button className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : "Save post"}</button><AdminRouteLink href="/admin/blog" className="btn btn-ghost">Cancel</AdminRouteLink></div>
    </form>
  </AdminShell>;
}
