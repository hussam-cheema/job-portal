"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AdminRouteLink } from "@/components/AdminRouteLink";
import { AdminShell } from "@/components/AdminShell";
import { adminDeletePage, adminListPages } from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import type { PageItem } from "@/lib/types";
import { formatDate } from "@/lib/format";

export default function AdminPagesListPage() {
  const { token } = useAdminAuth();
  const [pages, setPages] = useState<PageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function load() {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setPages(await adminListPages(token));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load pages");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function onDelete(id: string) {
    if (!token || !confirm("Delete this page?")) return;
    try {
      await adminDeletePage(token, id);
      setPages((prev) => prev.filter((p) => p.id !== id));
      setSuccess("Page deleted.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <AdminShell>
      <div className="card-panel">
        <div className="px-4 sm:px-5 py-4 border-b border-[var(--border)] flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
          <div>
            <h2 className="font-semibold text-[var(--navy-100)]">Pages</h2>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              CMS pages · create and edit in a full form
            </p>
          </div>
          <AdminRouteLink href="/admin/pages/new" className="btn btn-primary w-full sm:w-auto">
            New page
          </AdminRouteLink>
        </div>

        {loading && <p className="p-5 text-sm text-[var(--muted)]">Loading…</p>}
        {error && <p className="p-5 field-error">{error}</p>}
        {success && <p className="px-5 pt-4 text-sm text-[var(--success)] font-medium">{success}</p>}
        {!loading && pages.length === 0 && (
          <p className="p-5 text-sm text-[var(--muted)]">No pages yet. Create your first page.</p>
        )}

        <div className="divide-y divide-[var(--border)]">
          {pages.map((p) => (
            <div
              key={p.id}
              className="px-4 sm:px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3 justify-between"
            >
              <div className="min-w-0">
                <div className="font-medium text-[var(--navy-100)] break-words">{p.title}</div>
                <div className="text-xs text-[var(--muted)] mt-1 flex flex-wrap gap-x-2 gap-y-1">
                  <span>/{p.slug}</span>
                  <span>·</span>
                  <span>{p.is_published ? "Published" : "Draft"}</span>
                  {p.updated_at && (
                    <>
                      <span>·</span>
                      <span>Updated {formatDate(p.updated_at)}</span>
                    </>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 shrink-0">
                <Link
                  href={
                    ["about", "contact", "privacy"].includes(p.slug)
                      ? `/${p.slug}`
                      : `/p/${p.slug}`
                  }
                  className="btn btn-ghost"
                >
                  View
                </Link>
                <AdminRouteLink href={`/admin/pages/${p.id}`} className="btn btn-ghost">
                  Edit
                </AdminRouteLink>
                <button type="button" className="btn btn-ghost" onClick={() => onDelete(p.id)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </AdminShell>
  );
}
