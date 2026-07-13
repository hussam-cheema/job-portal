"use client";

import Link from "next/link";
import { AdminShell } from "@/components/AdminShell";

export default function AdminHome() {
  return (
    <AdminShell>
      <div className="card-panel p-6 space-y-4">
        <h2 className="text-xl font-semibold text-[var(--navy-100)]">Dashboard</h2>
        <p className="text-sm text-[var(--muted)]">
          Create and manage job posts manually. Fetch YouTube QnA per job. Edit CMS pages and
          review contact messages.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Link href="/admin/jobs/new" className="btn btn-primary">
            Create job post
          </Link>
          <Link href="/admin/pages/new" className="btn btn-primary">
            Create page
          </Link>
          <Link href="/admin/jobs" className="btn btn-ghost">
            Manage jobs
          </Link>
          <Link href="/admin/pages" className="btn btn-ghost">
            Manage pages
          </Link>
          <Link href="/admin/messages" className="btn btn-ghost">
            Contact messages
          </Link>
          <Link href="/admin/seo" className="btn btn-ghost">
            SEO monitor
          </Link>
        </div>
      </div>
    </AdminShell>
  );
}
