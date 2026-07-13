"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AdminShell } from "@/components/AdminShell";
import { RichTextEditor } from "@/components/RichTextEditor";
import { YoastSEOPanel, type YoastSEOValue } from "@/components/YoastSEOPanel";
import { adminListPages, adminSavePage, API_BASE } from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import type { PageItem } from "@/lib/types";

function slugify(text: string) {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .slice(0, 80);
}

export default function AdminPageForm() {
  const params = useParams<{ id?: string }>();
  const isNew = !params?.id || params.id === "new";
  const pageId = isNew ? null : String(params.id);
  const { token } = useAdminAuth();
  const router = useRouter();

  const [form, setForm] = useState({
    slug: "",
    title: "",
    content: "",
    is_published: true,
  });
  const [seo, setSeo] = useState<YoastSEOValue>({
    focus_keyword: "",
    meta_title: "",
    meta_description: "",
    meta_keywords: "",
  });
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [slugTouched, setSlugTouched] = useState(false);

  useEffect(() => {
    if (!token || !pageId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    adminListPages(token)
      .then((pages) => {
        if (cancelled) return;
        const page = pages.find((p: PageItem) => p.id === pageId);
        if (!page) {
          setError("Page not found");
          setLoading(false);
          return;
        }
        setForm({
          slug: page.slug,
          title: page.title,
          content: page.content,
          is_published: page.is_published,
        });
        setSlugTouched(true);
        return fetch(`${API_BASE}/api/seo/page/${page.id}`)
          .then((r) => (r.ok ? r.json() : null))
          .then((meta) => {
            if (!meta || cancelled) return;
            setSeo({
              focus_keyword: meta.focus_keyword || "",
              meta_title: meta.meta_title || "",
              meta_description: meta.meta_description || "",
              meta_keywords: meta.meta_keywords || "",
            });
          });
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load page");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, pageId]);

  function onTitleChange(title: string) {
    setForm((prev) => ({
      ...prev,
      title,
      slug: slugTouched ? prev.slug : slugify(title),
    }));
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    if (!form.title.trim() || !form.slug.trim()) {
      setError("Title and slug are required.");
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const saved = await adminSavePage(token, {
        id: pageId || undefined,
        slug: form.slug.trim(),
        title: form.title.trim(),
        content: form.content,
        is_published: form.is_published,
        seo: {
          focus_keyword: seo.focus_keyword || null,
          meta_title: seo.meta_title || null,
          meta_description: seo.meta_description || null,
          meta_keywords: seo.meta_keywords || null,
        },
      });
      setSuccess(pageId ? "Page updated successfully." : "Page saved successfully.");
      if (!pageId && saved?.id) {
        router.push(`/admin/pages/${saved.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Page could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <AdminShell>
        <div className="card-panel p-6 text-sm text-[var(--muted)]">Loading page…</div>
      </AdminShell>
    );
  }

  return (
    <AdminShell>
      <form onSubmit={onSave} className="card-panel p-4 sm:p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-[var(--navy-100)]">
              {isNew ? "Create page" : "Edit page"}
            </h2>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              Full content editor with Yoast SEO
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/admin/pages" className="btn btn-ghost">
              ← All pages
            </Link>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving…" : "Save page"}
            </button>
          </div>
        </div>

        {error && <p className="field-error">{error}</p>}
        {success && <p className="text-sm text-[var(--success)] font-medium">{success}</p>}

        <div>
          <label className="field-label">Title *</label>
          <input
            className="input"
            value={form.title}
            onChange={(e) => onTitleChange(e.target.value)}
            required
            placeholder="Page title"
          />
        </div>

        <div>
          <label className="field-label">Slug * (URL path)</label>
          <div className="flex flex-col sm:flex-row sm:items-center gap-2">
            <span className="text-sm text-[var(--muted)] shrink-0">/</span>
            <input
              className="input"
              value={form.slug}
              onChange={(e) => {
                setSlugTouched(true);
                setForm({ ...form, slug: slugify(e.target.value) || e.target.value });
              }}
              required
              placeholder="about-us"
            />
          </div>
        </div>

        <div>
          <label className="field-label">Content</label>
          <RichTextEditor
            key={`page-content-${pageId || "new"}`}
            value={form.content}
            onChange={(html) => setForm({ ...form, content: html })}
            placeholder="Write page content…"
          />
        </div>

        <label className="flex items-center gap-2 text-sm text-[var(--navy-200)]">
          <input
            type="checkbox"
            checked={form.is_published}
            onChange={(e) => setForm({ ...form, is_published: e.target.checked })}
          />
          Published (visible on the website)
        </label>

        <YoastSEOPanel
          title={form.title}
          content={form.content}
          slug={form.slug}
          value={seo}
          onChange={setSeo}
        />

        <div className="flex flex-wrap gap-2 pt-2 border-t border-[var(--border)]">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Saving…" : "Save page"}
          </button>
          <Link href="/admin/pages" className="btn btn-ghost">
            Cancel
          </Link>
        </div>
      </form>
    </AdminShell>
  );
}
