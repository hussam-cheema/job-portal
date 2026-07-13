"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { useAdminAuth } from "@/lib/adminAuth";
import { adminAnalytics } from "@/lib/api";
import type { AnalyticsDashboard } from "@/lib/types";

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function AnalyticsPage() {
  const { token } = useAdminAuth();
  const [month, setMonth] = useState(currentMonth);
  const [data, setData] = useState<AnalyticsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setData(await adminAnalytics(token, month));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analytics could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [month, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const chart = useMemo(() => {
    if (!data) return [];
    const [year, monthNumber] = data.month.split("-").map(Number);
    const days = new Date(year, monthNumber, 0).getDate();
    const indexed = new Map(data.daily.map((point) => [point.date, point]));
    return Array.from({ length: days }, (_, index) => {
      const date = `${data.month}-${String(index + 1).padStart(2, "0")}`;
      return indexed.get(date) || { date, visitors: 0, page_views: 0 };
    });
  }, [data]);
  const maxVisitors = Math.max(1, ...chart.map((point) => point.visitors));

  return (
    <AdminShell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-[var(--navy-100)]">Site analytics</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">Monthly visitors, page views, and locations.</p>
        </div>
        <div>
          <label className="field-label" htmlFor="analytics-month">Month</label>
          <input id="analytics-month" type="month" className="input" value={month} onChange={(event) => setMonth(event.target.value)} />
        </div>
      </div>
      {error && <p className="field-error mb-4">{error}</p>}
      {loading && !data ? (
        <div className="card-panel p-8 text-sm text-[var(--muted)]">Loading analytics…</div>
      ) : data ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="card-panel p-5">
              <p className="text-xs uppercase text-[var(--muted)]">Unique visitors</p>
              <p className="mt-2 text-3xl font-semibold tabular-nums text-[var(--navy-100)]">{data.unique_visitors.toLocaleString()}</p>
            </div>
            <div className="card-panel p-5">
              <p className="text-xs uppercase text-[var(--muted)]">Page views</p>
              <p className="mt-2 text-3xl font-semibold tabular-nums text-[var(--navy-100)]">{data.page_views.toLocaleString()}</p>
            </div>
          </div>

          <section className="card-panel mt-5 p-5">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-semibold text-[var(--navy-100)]">Daily visitors</h3>
              <span className="text-xs text-[var(--muted)]">{data.month}</span>
            </div>
            <div className="mt-6 flex h-56 items-end gap-1 border-b border-[var(--border)]" role="img" aria-label={`Daily unique visitors for ${data.month}`}>
              {chart.map((point, index) => (
                <div key={point.date} className="group relative flex h-full min-w-0 flex-1 items-end">
                  <div
                    className="w-full min-h-px bg-[var(--accent)] transition-opacity hover:opacity-75"
                    style={{ height: `${(point.visitors / maxVisitors) * 100}%` }}
                  />
                  <span className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-[var(--navy-700)] px-2 py-1 text-[10px] text-white group-hover:block">
                    Day {index + 1}: {point.visitors} visitors
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="card-panel mt-5 overflow-x-auto">
            <div className="border-b border-[var(--border)] px-5 py-4">
              <h3 className="font-semibold text-[var(--navy-100)]">Visitors by location</h3>
            </div>
            <table className="w-full text-left text-sm">
              <thead><tr><th>Country</th><th>Region</th><th>Visitors</th><th>Page views</th></tr></thead>
              <tbody>
                {data.locations.length ? data.locations.map((location) => (
                  <tr key={`${location.country}-${location.region || ""}`}>
                    <td>{location.country}</td>
                    <td>{location.region || "—"}</td>
                    <td>{location.visitors.toLocaleString()}</td>
                    <td>{location.page_views.toLocaleString()}</td>
                  </tr>
                )) : (
                  <tr><td colSpan={4} className="text-center text-[var(--muted)]">No visits recorded for this month.</td></tr>
                )}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </AdminShell>
  );
}
