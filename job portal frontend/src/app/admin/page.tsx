"use client";

import { AdminShell } from "@/components/AdminShell";
import { AdminRouteLink } from "@/components/AdminRouteLink";

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
          <AdminRouteLink href="/admin/jobs/new" className="btn btn-primary">
            Create job post
          </AdminRouteLink>
          <AdminRouteLink href="/admin/pages/new" className="btn btn-primary">
            Create page
          </AdminRouteLink>
          <AdminRouteLink href="/admin/jobs" className="btn btn-ghost">
            Manage jobs
          </AdminRouteLink>
          <AdminRouteLink href="/admin/pages" className="btn btn-ghost">
            Manage pages
          </AdminRouteLink>
          <AdminRouteLink href="/admin/messages" className="btn btn-ghost">
            Contact messages
          </AdminRouteLink>
          <AdminRouteLink href="/admin/seo" className="btn btn-ghost">
            SEO monitor
          </AdminRouteLink>
        </div>
      </div>
    </AdminShell>
  );
}
