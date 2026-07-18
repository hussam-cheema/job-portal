"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AdminRouteLink } from "@/components/AdminRouteLink";
import { AdminShell } from "@/components/AdminShell";
import { RichTextEditor } from "@/components/RichTextEditor";
import { TagInput } from "@/components/TagInput";
import { YoastSEOPanel, type YoastSEOValue } from "@/components/YoastSEOPanel";
import { API_BASE, adminGetBlogPost, adminSaveBlogPost } from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";

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

export default function AdminBlogFormPage() {
  const params = useParams<{ id?: string }>();
  const router = useRouter();
  const isNew = !params?.id || params.id === "new";
  const postId = isNew ? null : String(params.id);
  const { token } = useAdminAuth();
  const [form, setForm] = useState({
    title: "", slug: "", excerpt: "", content: "", author: "", category: "",
    tags: [] as string[], is_published: false, published_at: "",
  });
  const [seo, setSeo] = useState<YoastSEOValue>({ focus_keyword: "", meta_title: "", meta_description: "", meta_keywords: "" });
  const [slugTouched, setSlugTouched] = useState(false);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!token || !postId) { setLoading(false); return; }
    let cancelled = false;
    Promise.all([
      adminGetBlogPost(token, postId),
      fetch(`${API_BASE}/api/seo/blog/${postId}`, { cache: "no-store" }).then((r) => r.ok ? r.json() : null),
    ]).then(([post, meta]) => {
      if (cancelled) return;
      setForm({
        title: post.title, slug: post.slug, excerpt: post.excerpt || "", content: post.content,
        author: post.author || "", category: post.category || "", tags: post.tags || [],
        is_published: post.is_published, published_at: toDateTimeInput(post.published_at),
      });
      setSlugTouched(true);
      if (meta) setSeo({ focus_keyword: meta.focus_keyword || "", meta_title: meta.meta_title || "", meta_description: meta.meta_description || "", meta_keywords: meta.meta_keywords || "" });
    }).catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Failed to load blog post"))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [postId, token]);

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
      <div><label className="field-label">Title *</label><input className="input" value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value, slug: slugTouched ? p.slug : slugify(e.target.value) }))} required /></div>
      <div><label className="field-label">Slug *</label><div className="flex items-center gap-2"><span className="text-sm text-[var(--muted)]">/blog/</span><input className="input" value={form.slug} onChange={(e) => { setSlugTouched(true); setForm((p) => ({ ...p, slug: slugify(e.target.value) })); }} required /></div></div>
      <div><label className="field-label">Excerpt</label><textarea className="input min-h-24" value={form.excerpt} onChange={(e) => setForm({ ...form, excerpt: e.target.value })} maxLength={600} placeholder="A concise summary shown in the blog listing" /></div>
      <div className="grid gap-4 sm:grid-cols-2"><div><label className="field-label">Author</label><input className="input" value={form.author} onChange={(e) => setForm({ ...form, author: e.target.value })} /></div><div><label className="field-label">Category</label><input className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="Career Advice" /></div></div>
      <div><label className="field-label">Tags</label><TagInput values={form.tags} onChange={(tags) => setForm({ ...form, tags })} placeholder="Type a tag and press Enter" /></div>
      <div><label className="field-label">Article content</label><RichTextEditor key={`blog-${postId || "new"}`} value={form.content} onChange={(content) => setForm({ ...form, content })} placeholder="Write the blog post…" /></div>
      <div className="grid gap-4 sm:grid-cols-2"><label className="flex items-center gap-2 text-sm text-[var(--navy-200)]"><input type="checkbox" checked={form.is_published} onChange={(e) => setForm({ ...form, is_published: e.target.checked })} /> Published</label><div><label className="field-label">Publish date and time</label><input type="datetime-local" className="input" value={form.published_at} onChange={(e) => setForm({ ...form, published_at: e.target.value })} /></div></div>
      <YoastSEOPanel title={form.title} content={form.content} slug={`blog/${form.slug}`} value={seo} onChange={setSeo} />
      <div className="flex gap-2 border-t border-[var(--border)] pt-5"><button className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : "Save post"}</button><AdminRouteLink href="/admin/blog" className="btn btn-ghost">Cancel</AdminRouteLink></div>
    </form>
  </AdminShell>;
}
