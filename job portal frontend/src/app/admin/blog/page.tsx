"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AdminRouteLink } from "@/components/AdminRouteLink";
import { AdminShell } from "@/components/AdminShell";
import { EditorDraftsPanel } from "@/components/EditorDraftsPanel";
import { adminDeleteBlogPost, adminListBlogPosts } from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import { formatDate } from "@/lib/format";
import type { BlogListResponse } from "@/lib/types";

export default function AdminBlogPage() {
  const { token } = useAdminAuth();
  const [result, setResult] = useState<BlogListResponse>({ items: [], total: 0, page: 1, page_size: 25, pages: 0 });
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (page = 1) => {
    if (!token) return;
    setLoading(true); setError("");
    try { setResult(await adminListBlogPosts(token, { q, status, page })); }
    catch (e) { setError(e instanceof Error ? e.message : "Failed to load blog posts"); }
    finally { setLoading(false); }
  }, [q, status, token]);

  useEffect(() => { void load(); }, [load]);

  async function remove(id: string) {
    if (!token || !confirm("Delete this blog post permanently?")) return;
    try { await adminDeleteBlogPost(token, id); await load(result.page); }
    catch (e) { setError(e instanceof Error ? e.message : "Delete failed"); }
  }

  return <AdminShell>
    <EditorDraftsPanel kind="blog" />
    <div className="card-panel overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-[var(--border)] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div><h2 className="font-semibold text-[var(--navy-100)]">Blog posts</h2><p className="text-xs text-[var(--muted)]">Create, publish, and optimize articles</p></div>
        <AdminRouteLink href="/admin/blog/new" className="btn btn-primary">New blog post</AdminRouteLink>
      </div>
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); void load(); }} className="grid gap-2 border-b border-[var(--border)] p-4 sm:grid-cols-[1fr_12rem_auto]">
        <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search posts…" aria-label="Search blog posts" />
        <select className="input" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Publication status"><option value="">All statuses</option><option value="published">Published</option><option value="draft">Draft</option></select>
        <button className="btn btn-ghost">Filter</button>
      </form>
      {loading && <p className="p-5 text-sm text-[var(--muted)]">Loading…</p>}
      {error && <p className="p-5 field-error">{error}</p>}
      {!loading && !result.items.length && <p className="p-5 text-sm text-[var(--muted)]">No blog posts yet.</p>}
      <div className="divide-y divide-[var(--border)]">
        {result.items.map((post) => <div key={post.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0"><div className="font-medium text-[var(--navy-100)]">{post.title}</div><div className="mt-1 text-xs text-[var(--muted)]">/{post.slug} · {post.is_published ? "Published" : "Draft"} · Updated {formatDate(post.updated_at)}</div></div>
          <div className="flex gap-2">{post.is_published && <Link href={`/blog/${post.slug}`} className="btn btn-ghost">View</Link>}<AdminRouteLink href={`/admin/blog/${post.id}`} className="btn btn-ghost">Edit</AdminRouteLink><button type="button" className="btn btn-ghost" onClick={() => void remove(post.id)}>Delete</button></div>
        </div>)}
      </div>
      {result.pages > 1 && <div className="flex justify-end gap-2 border-t border-[var(--border)] p-4"><button className="btn btn-ghost" disabled={result.page <= 1} onClick={() => void load(result.page - 1)}>← Previous</button><span className="self-center text-sm text-[var(--muted)]">Page {result.page} of {result.pages}</span><button className="btn btn-ghost" disabled={result.page >= result.pages} onClick={() => void load(result.page + 1)}>Next →</button></div>}
    </div>
  </AdminShell>;
}
