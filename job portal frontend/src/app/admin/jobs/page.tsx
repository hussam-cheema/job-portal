"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AdminRouteLink } from "@/components/AdminRouteLink";
import { AdminShell } from "@/components/AdminShell";
import { EditorDraftsPanel } from "@/components/EditorDraftsPanel";
import { adminDeleteJob, adminListJobs } from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import type { JobSummary } from "@/lib/types";
import { formatDate } from "@/lib/format";

export default function AdminJobsPage() {
  const { token } = useAdminAuth();
  const [items, setItems] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!token) return;
    setLoading(true);
    try {
      const data = await adminListJobs(token, 1);
      setItems(data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function onDelete(id: string) {
    if (!token || !confirm("Delete this job post?")) return;
    try {
      await adminDeleteJob(token, id);
      setItems((prev) => prev.filter((j) => j.id !== id));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <AdminShell>
      <EditorDraftsPanel kind="job" />
      <div className="card-panel">
        <div className="px-5 py-4 border-b border-[var(--border)] flex items-center justify-between">
          <h2 className="font-semibold text-[var(--navy-100)]">Job posts</h2>
          <AdminRouteLink href="/admin/jobs/new" className="btn btn-primary">
            New job
          </AdminRouteLink>
        </div>
        {loading && <p className="p-5 text-sm text-[var(--muted)]">Loading…</p>}
        {error && <p className="p-5 field-error">{error}</p>}
        {!loading && items.length === 0 && (
          <p className="p-5 text-sm text-[var(--muted)]">No jobs yet. Create your first post.</p>
        )}
        <div className="divide-y divide-[var(--border)]">
          {items.map((job) => (
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
      </div>
    </AdminShell>
  );
}
