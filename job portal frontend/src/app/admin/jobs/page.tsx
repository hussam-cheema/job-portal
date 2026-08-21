"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AdminRouteLink } from "@/components/AdminRouteLink";
import { AdminShell } from "@/components/AdminShell";
import { EditorDraftsPanel } from "@/components/EditorDraftsPanel";
import { adminDeleteJob, adminListJobs } from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import type { JobListResponse } from "@/lib/types";
import { formatDate } from "@/lib/format";

export default function AdminJobsPage() {
  const { token } = useAdminAuth();
  const [result, setResult] = useState<JobListResponse>({
    items: [],
    total: 0,
    page: 1,
    page_size: 25,
    pages: 0,
  });
  const [draftCount, setDraftCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (page = 1) => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await adminListJobs(token, page));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onDelete(id: string) {
    if (!token || !confirm("Delete this job post?")) return;
    try {
      await adminDeleteJob(token, id);
      const targetPage = result.items.length === 1 && result.page > 1
        ? result.page - 1
        : result.page;
      await load(targetPage);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <AdminShell>
      <div className="card-panel">
        <div className="px-5 py-4 border-b border-[var(--border)] flex items-center justify-between gap-4">
          <div>
            <h2 className="font-semibold text-[var(--navy-100)]">Job posts</h2>
            <p className="mt-1 text-xs text-[var(--muted)]">
              {result.total} total job post{result.total === 1 ? "" : "s"}
            </p>
          </div>
          <AdminRouteLink href="/admin/jobs/new" className="btn btn-primary">
            New job
          </AdminRouteLink>
        </div>
        {loading && <p className="p-5 text-sm text-[var(--muted)]">Loading…</p>}
        {error && <p className="p-5 field-error">{error}</p>}
        {!loading && result.items.length === 0 && draftCount === 0 && (
          <p className="p-5 text-sm text-[var(--muted)]">No jobs yet. Create your first post.</p>
        )}
        <div className="divide-y divide-[var(--border)]">
          <EditorDraftsPanel kind="job" onCountChange={setDraftCount} />
          {result.items.map((job) => (
            <div key={job.id} className="px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
              <div>
                <div className="font-medium text-[var(--navy-100)]">{job.title}</div>
                <div className="text-xs text-[var(--muted)] mt-1">
                  {formatDate(job.published_date)} · {job.job_type || job.source_type} ·{" "}
                  {(job.cities || []).join(", ") || job.city || "—"}
                </div>
              </div>
              <div className="flex gap-2">
                <Link href={`/jobs/${job.slug || job.id}`} className="btn btn-ghost">
                  View
                </Link>
                <AdminRouteLink href={`/admin/jobs/${job.id}`} className="btn btn-ghost">
                  Edit
                </AdminRouteLink>
                <button type="button" className="btn btn-ghost" onClick={() => onDelete(job.id)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
        {result.total > 0 && (
          <div className="flex flex-col items-center justify-between gap-3 border-t border-[var(--border)] px-5 py-4 sm:flex-row">
            <p className="text-sm text-[var(--muted)]">
              Showing {(result.page - 1) * result.page_size + 1}–{Math.min(result.page * result.page_size, result.total)} of {result.total}
            </p>
            <div className="flex items-center gap-2" aria-label="Job posts pagination">
              <button
                type="button"
                className="btn btn-ghost"
                disabled={loading || result.page <= 1}
                onClick={() => void load(result.page - 1)}
              >
                ← Previous
              </button>
              <span className="px-2 text-sm text-[var(--muted)]">
                Page {result.page} of {Math.max(result.pages, 1)}
              </span>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={loading || result.page >= result.pages}
                onClick={() => void load(result.page + 1)}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </AdminShell>
  );
}
