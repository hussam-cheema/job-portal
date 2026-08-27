"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { useAdminAuth } from "@/lib/adminAuth";
import { adminAnalytics, adminRealtimeAnalytics } from "@/lib/api";
import type { AnalyticsDashboard, AnalyticsRealtime } from "@/lib/types";

function currentMonth() {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Karachi",
    year: "numeric",
    month: "2-digit",
  }).formatToParts(new Date());
  const year = parts.find((part) => part.type === "year")?.value;
  const month = parts.find((part) => part.type === "month")?.value;
  return `${year}-${month}`;
}

export default function AnalyticsPage() {
  const { token } = useAdminAuth();
  const [month, setMonth] = useState(currentMonth);
  const [data, setData] = useState<AnalyticsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [realtime, setRealtime] = useState<AnalyticsRealtime | null>(null);
  const [realtimeError, setRealtimeError] = useState<string | null>(null);

  const load = useCallback(async (background = false) => {
    if (!token) return;
    if (!background) setLoading(true);
    try {
      setData(await adminAnalytics(token, month));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analytics could not be loaded");
    } finally {
      if (!background) setLoading(false);
    }
  }, [month, token]);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(true), 60_000);
    return () => window.clearInterval(interval);
  }, [load]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    const loadRealtime = async () => {
      try {
        const result = await adminRealtimeAnalytics(token, 5);
        if (!cancelled) {
          setRealtime(result);
          setRealtimeError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setRealtimeError(err instanceof Error ? err.message : "Live analytics unavailable");
        }
      }
    };
    void loadRealtime();
    const interval = window.setInterval(() => void loadRealtime(), 10_000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [token]);

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
          <p className="mt-1 text-sm text-[var(--muted)]">Unique browsers, page views, and locations in Pakistan time.</p>
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
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="card-panel p-5">
              <p className="flex items-center gap-2 text-xs uppercase text-[var(--muted)]">
                <span className="h-2 w-2 rounded-full bg-emerald-500 motion-safe:animate-pulse" />
                Active now
              </p>
              <p className="mt-2 text-3xl font-semibold tabular-nums text-[var(--navy-100)]">
                {(realtime?.active_visitors || 0).toLocaleString()}
              </p>
              <p className="mt-1 text-xs text-[var(--muted)]">Last {realtime?.window_minutes || 5} minutes</p>
            </div>
            <div className="card-panel p-5">
              <p className="text-xs uppercase text-[var(--muted)]">Unique browsers</p>
              <p className="mt-2 text-3xl font-semibold tabular-nums text-[var(--navy-100)]">{data.unique_visitors.toLocaleString()}</p>
              <p className="mt-1 text-xs text-[var(--muted)]">Selected month • PKT</p>
            </div>
            <div className="card-panel p-5">
              <p className="text-xs uppercase text-[var(--muted)]">Page views</p>
              <p className="mt-2 text-3xl font-semibold tabular-nums text-[var(--navy-100)]">{data.page_views.toLocaleString()}</p>
            </div>
          </div>

          {realtimeError && <p className="field-error mt-4">{realtimeError}</p>}
          <section className="card-panel mt-5 overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-5 py-4">
              <h3 className="font-semibold text-[var(--navy-100)]">Realtime pages</h3>
              <span className="text-xs text-[var(--muted)]">Refreshes every 10 seconds</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="bg-[var(--navy-850)]">
                  <tr>
                    <th className="px-5 py-3">Page</th>
                    <th className="px-5 py-3">Visitors</th>
                    <th className="px-5 py-3">Last seen</th>
                  </tr>
                </thead>
                <tbody>
                  {realtime?.pages.length ? realtime.pages.map((page) => (
                    <tr key={page.path} className="border-t border-[var(--border)]">
                      <td className="px-5 py-3 font-mono text-xs">{page.path}</td>
                      <td className="px-5 py-3 tabular-nums">{page.visitors}</td>
                      <td className="px-5 py-3 text-[var(--muted)]">
                        {new Date(page.last_seen).toLocaleTimeString()}
                      </td>
                    </tr>
                  )) : (
                    <tr><td colSpan={3} className="px-5 py-6 text-center text-[var(--muted)]">No active visitors in the last five minutes.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card-panel mt-5 overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-5 py-4">
              <h3 className="font-semibold text-[var(--navy-100)]">Realtime visitor locations</h3>
              <span className="text-xs text-[var(--muted)]">
                Privacy-safe aggregated locations
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] text-left text-sm">
                <thead className="bg-[var(--navy-850)]">
                  <tr>
                    <th className="px-5 py-3">Country</th>
                    <th className="px-5 py-3">Region</th>
                    <th className="px-5 py-3">City</th>
                    <th className="px-5 py-3">Active visitors</th>
                    <th className="px-5 py-3">Last seen</th>
                  </tr>
                </thead>
                <tbody>
                  {realtime?.locations.length ? realtime.locations.map((location) => (
                    <tr
                      key={`${location.country}-${location.region || ""}-${location.city || ""}`}
                      className="border-t border-[var(--border)]"
                    >
                      <td className="px-5 py-3">{location.country}</td>
                      <td className="px-5 py-3">{location.region || "—"}</td>
                      <td className="px-5 py-3">{location.city || "—"}</td>
                      <td className="px-5 py-3 tabular-nums">{location.visitors}</td>
                      <td className="px-5 py-3 text-[var(--muted)]">
                        {new Date(location.last_seen).toLocaleTimeString()}
                      </td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan={5} className="px-5 py-6 text-center text-[var(--muted)]">
                        No active visitor locations in the last five minutes.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card-panel mt-5 p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="font-semibold text-[var(--navy-100)]">Daily unique browsers</h3>
                <p className="mt-1 text-xs text-[var(--muted)]">Pakistan time (PKT) • refreshes every 60 seconds</p>
              </div>
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
                    Day {index + 1}: {point.visitors} unique browsers
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="card-panel mt-5 overflow-hidden">
            <div className="border-b border-[var(--border)] px-5 py-4">
              <h3 className="font-semibold text-[var(--navy-100)]">Visitors by location</h3>
            </div>
            <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="bg-[var(--navy-850)]"><tr><th className="px-5 py-3">Country</th><th className="px-5 py-3">Region</th><th className="px-5 py-3">City</th><th className="px-5 py-3">Visitors</th><th className="px-5 py-3">Page views</th></tr></thead>
              <tbody className="divide-y divide-[var(--border)]">
                {data.locations.length ? data.locations.map((location) => (
                  <tr key={`${location.country}-${location.region || ""}-${location.city || ""}`}>
                    <td className="px-5 py-3">{location.country}</td>
                    <td className="px-5 py-3">{location.region || "—"}</td>
                    <td className="px-5 py-3">{location.city || "—"}</td>
                    <td className="px-5 py-3 tabular-nums">{location.visitors.toLocaleString()}</td>
                    <td className="px-5 py-3 tabular-nums">{location.page_views.toLocaleString()}</td>
                  </tr>
                )) : (
                  <tr><td colSpan={5} className="px-5 py-6 text-center text-[var(--muted)]">No visits recorded for this month.</td></tr>
                )}
              </tbody>
            </table>
            </div>
          </section>
        </>
      ) : null}
    </AdminShell>
  );
}
