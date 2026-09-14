"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { adminToolAnalytics } from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import type { ToolAnalytics } from "@/lib/types";

function pakistanMonth() {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Karachi", year: "numeric", month: "2-digit",
  }).formatToParts(new Date());
  const year = parts.find((part) => part.type === "year")?.value;
  const month = parts.find((part) => part.type === "month")?.value;
  return `${year}-${month}`;
}

function monthLabel(month: string) {
  const [year, number] = month.split("-").map(Number);
  return new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(new Date(year, number - 1, 1));
}

export default function ToolsAnalyticsPage() {
  const { token } = useAdminAuth();
  const [month, setMonth] = useState(pakistanMonth);
  const [data, setData] = useState<ToolAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (background = false) => {
    if (!token) return;
    if (!background) setLoading(true);
    try {
      setData(await adminToolAnalytics(token, month));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tool analytics could not be loaded");
    } finally {
      if (!background) setLoading(false);
    }
  }, [month, token]);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(true), 60_000);
    return () => window.clearInterval(interval);
  }, [load]);

  const categories = useMemo(() => {
    const grouped = new Map<string, ToolAnalytics["tools"]>();
    for (const tool of data?.tools || []) {
      const rows = grouped.get(tool.category_title) || [];
      rows.push(tool);
      grouped.set(tool.category_title, rows);
    }
    return Array.from(grouped.entries());
  }, [data]);
  const largestUseCount = Math.max(1, ...(data?.tools.map((tool) => tool.uses) || []));

  return <AdminShell>
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <p className="admin-eyebrow">Tools hub · performance</p>
        <h2 className="mt-1 text-2xl font-semibold text-[var(--navy-100)]">Tools Analytics</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
          Monthly engagement for every tool, including newly created and unpublished tools.
        </p>
      </div>
      <div className="flex w-full flex-wrap items-end gap-2 sm:w-auto">
        <div className="min-w-[175px] flex-1 sm:flex-none">
          <label className="field-label" htmlFor="tools-analytics-month">Month · Pakistan time</label>
          <input id="tools-analytics-month" type="month" className="input" value={month} onChange={(event) => setMonth(event.target.value)} />
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => void load()} disabled={loading}>Refresh</button>
      </div>
    </div>

    {error && <p role="alert" className="field-error mb-4">{error}</p>}
    {loading && !data ? <div className="card-panel p-8 text-sm text-[var(--muted)]">Loading tool analytics…</div> : data && <>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="card-panel p-5"><p className="text-xs uppercase tracking-wide text-[var(--muted)]">Tool uses</p><p className="mt-2 text-3xl font-semibold tabular-nums text-[var(--navy-100)]">{data.total_uses.toLocaleString()}</p><p className="mt-1 text-xs text-[var(--muted)]">First meaningful interaction per browser and 30-minute window</p></div>
        <div className="card-panel p-5"><p className="text-xs uppercase tracking-wide text-[var(--muted)]">Tool opens</p><p className="mt-2 text-3xl font-semibold tabular-nums text-[var(--navy-100)]">{data.total_opens.toLocaleString()}</p><p className="mt-1 text-xs text-[var(--muted)]">Page opens, deduplicated in the same window</p></div>
        <div className="card-panel p-5"><p className="text-xs uppercase tracking-wide text-[var(--muted)]">Tools in directory</p><p className="mt-2 text-3xl font-semibold tabular-nums text-[var(--navy-100)]">{data.tools.length.toLocaleString()}</p><p className="mt-1 text-xs text-[var(--muted)]">New tools appear here automatically</p></div>
      </div>

      <section className="card-panel mt-5 p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--border)] pb-4">
          <div><h3 className="text-lg font-semibold text-[var(--navy-100)]">Usage by tool</h3><p className="mt-1 text-sm text-[var(--muted)]">{monthLabel(data.month)} · Asia/Karachi</p></div>
          <Link href="/admin/tools" className="text-sm font-semibold text-[var(--accent)] hover:underline">Manage tools →</Link>
        </div>
        {categories.length ? categories.map(([categoryName, tools]) => <div key={categoryName} className="mt-6">
          <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">{categoryName}</h4>
          <div className="space-y-3">{tools.map((tool) => <div key={tool.id} className="rounded-2xl border border-[var(--border)] p-4 sm:p-5" data-testid="tool-analytics-row">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0"><p className="font-semibold text-[var(--navy-100)]">{tool.title} {!tool.is_published && <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-normal text-slate-600">Unpublished</span>}</p><p className="mt-1 break-all text-xs text-[var(--muted)]">/tools/{tool.slug}</p></div>
              <div className="flex shrink-0 gap-5 text-right text-sm"><div><strong className="block tabular-nums text-[var(--navy-100)]">{tool.uses.toLocaleString()}</strong><span className="text-xs text-[var(--muted)]">uses</span></div><div><strong className="block tabular-nums text-[var(--navy-100)]">{tool.opens.toLocaleString()}</strong><span className="text-xs text-[var(--muted)]">opens</span></div></div>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-[var(--navy-850)]" role="img" aria-label={`${tool.title}: ${tool.uses} uses in ${monthLabel(data.month)}`}><div className="h-full rounded-full bg-[var(--accent)]" style={{ width: `${(tool.uses / largestUseCount) * 100}%` }} /></div>
          </div>)}</div>
        </div>) : <p className="py-8 text-sm text-[var(--muted)]">No tools have been created yet.</p>}
      </section>
      <p className="mt-4 text-xs leading-5 text-[var(--muted)]">Tracking starts with this release; earlier tool usage cannot be reconstructed. Repeated inputs in the same visit are counted once, and automated crawlers are excluded. Counts refresh every minute.</p>
    </>}
  </AdminShell>;
}
