"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { useAdminAuth } from "@/lib/adminAuth";
import { adminInfrastructure } from "@/lib/api";
import type {
  InfrastructureComputeMetric,
  InfrastructureDashboard,
  InfrastructureStorageMetric,
} from "@/lib/types";

type Sample = { at: number; cpu: number; memory: number };

const statusStyles: Record<string, string> = {
  healthy: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  managed: "border-blue-400/25 bg-blue-400/10 text-blue-300",
  warning: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  critical: "border-red-400/25 bg-red-400/10 text-red-300",
  unavailable: "border-slate-400/25 bg-slate-400/10 text-slate-300",
  unknown: "border-slate-400/25 bg-slate-400/10 text-slate-300",
  info: "border-blue-400/25 bg-blue-400/10 text-blue-300",
};

function formatBytes(value: number | null) {
  if (value === null) return "Unavailable";
  if (value === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const amount = value / 1024 ** index;
  return `${amount.toFixed(index > 2 ? 2 : index > 0 ? 1 : 0)} ${units[index]}`;
}

function formatUptime(seconds: number | null) {
  if (seconds === null) return "—";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${statusStyles[status] || statusStyles.unknown}`}>
      {status}
    </span>
  );
}

function Gauge({ value, color = "var(--accent)" }: { value: number | null; color?: string }) {
  const normalized = Math.min(100, Math.max(0, value ?? 0));
  return (
    <div className="relative h-24 w-24 shrink-0" role="img" aria-label={value === null ? "Usage unavailable" : `${value.toFixed(1)} percent used`}>
      <svg viewBox="0 0 42 42" className="h-full w-full -rotate-90">
        <circle cx="21" cy="21" r="16" fill="none" stroke="var(--navy-800)" strokeWidth="4" />
        <circle
          cx="21"
          cy="21"
          r="16"
          fill="none"
          pathLength="100"
          stroke={color}
          strokeDasharray={`${normalized} 100`}
          strokeLinecap="round"
          strokeWidth="4"
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-lg font-semibold tabular-nums text-[var(--navy-100)]">
        {value === null ? "—" : `${Math.round(value)}%`}
      </span>
    </div>
  );
}

function Progress({ value, color = "var(--accent)" }: { value: number | null; color?: string }) {
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-[var(--navy-800)]">
      <div
        className="h-full rounded-full transition-[width] duration-500"
        style={{ width: `${Math.min(100, Math.max(0, value ?? 0))}%`, backgroundColor: color }}
      />
    </div>
  );
}

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const points = (values.length > 1 ? values : [values[0] ?? 0, values[0] ?? 0])
    .map((value, index, list) => `${(index / (list.length - 1)) * 100},${34 - Math.min(100, Math.max(0, value)) * 0.3}`)
    .join(" ");
  return (
    <svg viewBox="0 0 100 38" preserveAspectRatio="none" className="h-16 w-full" aria-hidden="true">
      <path d="M0 34H100" stroke="var(--border-strong)" strokeWidth="0.7" />
      <polyline points={points} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

const providerColors: Record<string, string> = {
  Railway: "#a855f7",
  Neon: "#2dd4bf",
  "Microsoft Azure": "#60a5fa",
  "Cloudflare R2": "#f59e0b",
};

function CostHistoryChart({
  points,
}: {
  points: InfrastructureDashboard["costs"]["history"];
}) {
  const maximum = Math.max(1, ...points.map((point) => point.total_usd ?? 0));
  const providers = Object.keys(providerColors).filter((provider) =>
    points.some((point) => provider in point.provider_costs),
  );
  return (
    <div className="mt-6 border-t border-[var(--border)] pt-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-[var(--navy-200)]">Monthly cost history</h4>
          <p className="mt-1 text-xs text-[var(--muted)]">Stored snapshots and invoice backfills; unavailable months are shown as a dash.</p>
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {providers.map((provider) => (
            <span key={provider} className="inline-flex items-center gap-1.5 text-[10px] text-[var(--muted)]">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: providerColors[provider] }} />
              {provider}
            </span>
          ))}
        </div>
      </div>
      <div className="mt-5 flex h-40 items-end gap-1.5 overflow-x-auto border-b border-[var(--border-strong)] pb-1 sm:gap-2">
        {points.map((point) => {
          const total = point.total_usd;
          const paid = point.paid_usd ?? 0;
          const outstanding = point.outstanding_usd ?? total;
          const height = total !== null && total > 0 ? Math.max(6, (total / maximum) * 100) : 2;
          return (
            <div key={point.month} className="group flex min-w-10 flex-1 flex-col items-center justify-end sm:min-w-12">
              <p className="mb-1 text-[9px] tabular-nums text-[var(--muted)]">
                {total === null ? "—" : `$${total.toFixed(2)}`}
              </p>
              <div
                className="flex w-full max-w-10 flex-col-reverse overflow-hidden rounded-t-md bg-[var(--navy-800)] transition-opacity group-hover:opacity-80"
                style={{ height: `${height}%` }}
                title={`${point.month}: ${total === null ? "cost unavailable" : `$${total.toFixed(2)} billed · $${paid.toFixed(2)} paid · $${(outstanding ?? 0).toFixed(2)} due`} · ${point.source}${point.estimated ? " (estimated)" : ""}`}
              >
                {Object.entries(point.provider_costs)
                  .filter(([, cost]) => cost > 0)
                  .map(([provider, cost]) => (
                    <div
                      key={provider}
                      style={{
                        backgroundColor: providerColors[provider] || "#94a3b8",
                        flexGrow: cost,
                      }}
                    />
                  ))}
              </div>
              {total !== null && (
                <span className={`mt-1 text-[8px] ${outstanding === 0 && total > 0 ? "text-emerald-300" : "text-[var(--muted)]"}`}>
                  {outstanding === 0 && total > 0 ? "Paid" : `$${(outstanding ?? 0).toFixed(2)} due`}
                </span>
              )}
              <span className="mt-2 text-[9px] text-[var(--muted)]">
                {new Date(`${point.month}-01T00:00:00Z`).toLocaleDateString(undefined, {
                  month: "short",
                  year: points.length > 12 ? "2-digit" : undefined,
                  timeZone: "UTC",
                })}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StorageCard({ metric }: { metric?: InfrastructureStorageMetric }) {
  if (!metric) return null;
  const color = metric.status === "critical" ? "var(--danger)" : metric.status === "warning" ? "var(--gold)" : "var(--accent)";
  return (
    <article className="card-panel relative p-5">
      <div className="absolute -right-10 -top-10 h-28 w-28 rounded-full bg-blue-400/5 blur-2xl" />
      <div className="relative flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.12em] text-[var(--muted)]">{metric.provider}</p>
          <h3 className="mt-1 font-semibold text-[var(--navy-100)]">{metric.name}</h3>
        </div>
        <StatusBadge status={metric.status} />
      </div>
      <div className="relative mt-5 flex items-center gap-4">
        <Gauge value={metric.utilization_percent} color={color} />
        <div className="min-w-0">
          <p className="text-2xl font-semibold tabular-nums text-[var(--navy-100)]">{formatBytes(metric.used_bytes)}</p>
          <p className="mt-1 text-xs text-[var(--muted)]">of {formatBytes(metric.total_bytes)} tracked</p>
          {metric.object_count !== null && <p className="mt-3 text-xs text-[var(--navy-300)]">{metric.object_count.toLocaleString()} objects</p>}
        </div>
      </div>
      <div className="relative mt-4"><Progress value={metric.utilization_percent} color={color} /></div>
      <p className="relative mt-3 text-xs leading-5 text-[var(--muted)]">{metric.detail}</p>
    </article>
  );
}

function ComputeCard({ metric, history }: { metric?: InfrastructureComputeMetric; history: Sample[] }) {
  if (!metric) return null;
  return (
    <article className="card-panel p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.12em] text-[var(--muted)]">{metric.provider}</p>
          <h3 className="mt-1 text-lg font-semibold text-[var(--navy-100)]">{metric.name}</h3>
        </div>
        <StatusBadge status={metric.status} />
      </div>
      <div className="mt-6 grid gap-5 sm:grid-cols-2">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-4">
          <div className="flex items-center justify-between gap-4">
            <div><p className="text-xs uppercase tracking-wider text-[var(--muted)]">CPU utilization</p><p className="mt-2 text-2xl font-semibold tabular-nums text-[var(--navy-100)]">{metric.cpu_used_percent?.toFixed(1) ?? "—"}%</p><p className="mt-1 text-xs text-[var(--muted)]">{metric.cpu_allocated_cores ?? "—"} vCPU allocated</p></div>
            <Gauge value={metric.cpu_used_percent} />
          </div>
          <Sparkline values={history.map((item) => item.cpu)} color="var(--accent)" />
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-4">
          <div className="flex items-center justify-between gap-4">
            <div><p className="text-xs uppercase tracking-wider text-[var(--muted)]">Memory utilization</p><p className="mt-2 text-2xl font-semibold tabular-nums text-[var(--navy-100)]">{metric.memory_used_percent?.toFixed(1) ?? "—"}%</p><p className="mt-1 text-xs text-[var(--muted)]">{formatBytes(metric.memory_used_bytes)} / {formatBytes(metric.memory_allocated_bytes)}</p></div>
            <Gauge value={metric.memory_used_percent} color="var(--success)" />
          </div>
          <Sparkline values={history.map((item) => item.memory)} color="var(--success)" />
        </div>
      </div>
      <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 border-t border-[var(--border)] pt-4 text-xs text-[var(--muted)]">
        <span>Scale <strong className="font-medium text-[var(--navy-200)]">{metric.min_replicas}–{metric.max_replicas} replicas</strong></span>
        <span>Uptime <strong className="font-medium text-[var(--navy-200)]">{formatUptime(metric.uptime_seconds)}</strong></span>
        <span>{metric.runtime_model}</span>
      </div>
    </article>
  );
}

export default function InfrastructureAnalyticsPage() {
  const { token } = useAdminAuth();
  const [data, setData] = useState<InfrastructureDashboard | null>(null);
  const [history, setHistory] = useState<Sample[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (force = false) => {
    if (!token) return;
    setRefreshing(true);
    setError(null);
    try {
      const next = await adminInfrastructure(token, force);
      setData(next);
      const backend = next.compute.find((item) => item.id === "backend");
      if (backend && backend.cpu_used_percent !== null && backend.memory_used_percent !== null) {
        const cpu = backend.cpu_used_percent;
        const memory = backend.memory_used_percent;
        setHistory((current) => [...current, { at: Date.now(), cpu, memory }].slice(-20));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Infrastructure metrics could not be loaded");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), 30_000);
    return () => window.clearInterval(interval);
  }, [load]);

  const resources = useMemo(() => ({
    r2: data?.storage.find((item) => item.id === "r2"),
    database: data?.storage.find((item) => item.id === "database"),
    backend: data?.compute.find((item) => item.id === "backend"),
  }), [data]);

  return (
    <AdminShell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold text-[var(--navy-100)]">Infrastructure analytics</h2>
            {data && <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,.7)]" aria-label="Live telemetry" />}
          </div>
          <p className="mt-1 text-sm text-[var(--muted)]">Live capacity, backend performance, and paid-versus-outstanding infrastructure costs.</p>
        </div>
        <div className="flex items-center gap-3">
          {data && <p className="text-xs text-[var(--muted)]">Updated {new Date(data.collected_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</p>}
          <button type="button" className="btn btn-ghost" disabled={refreshing} onClick={() => void load(true)}>
            {refreshing ? "Refreshing…" : "Refresh now"}
          </button>
        </div>
      </div>

      {error && <div className="mb-5 rounded-xl border border-red-400/25 bg-red-400/10 p-4 text-sm text-red-300">{error}</div>}
      {loading && !data ? (
        <div className="card-panel p-10 text-center text-sm text-[var(--muted)]">Collecting infrastructure telemetry…</div>
      ) : data ? (
        <div className="space-y-5">
          <section className="grid gap-4 md:grid-cols-2">
            <StorageCard metric={resources.r2} />
            <StorageCard metric={resources.database} />
          </section>

          <section>
            <ComputeCard metric={resources.backend} history={history} />
          </section>

          <section>
            <article className="card-panel p-5 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.12em] text-[var(--muted)]">FinOps</p>
                  <h3 className="mt-1 text-lg font-semibold text-[var(--navy-100)]">
                    Monthly infrastructure cost
                  </h3>
                  <p className="mt-1 text-xs text-[var(--muted)]">{data.costs.source}</p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">Current outstanding</p>
                  <p><span className="text-2xl font-semibold tabular-nums text-[var(--navy-100)]">${(data.costs.current_outstanding_usd ?? data.costs.tracked_monthly_estimate_usd).toFixed(2)}</span><span className="text-xs text-[var(--muted)]"> / ${data.costs.monthly_budget_usd.toFixed(0)}</span></p>
                </div>
              </div>
              {data.costs.forecast_monthly_cost_usd !== null && (
                <p className="mt-3 text-sm text-[var(--muted)]">
                  Provider forecast:{" "}
                  <strong className="text-[var(--navy-200)]">
                    ${data.costs.forecast_monthly_cost_usd.toFixed(2)}
                  </strong>
                </p>
              )}
              <div className="mt-5"><Progress value={data.costs.budget_utilization_percent} color="var(--gold)" /></div>
              <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  ["Current billed", data.costs.current_month_cost_usd ?? data.costs.tracked_monthly_estimate_usd],
                  ["Current paid", data.costs.current_month_paid_usd ?? 0],
                  ["Recorded total", data.costs.recorded_total_usd ?? data.costs.tracked_monthly_estimate_usd],
                  ["Total outstanding", data.costs.recorded_outstanding_usd ?? data.costs.tracked_monthly_estimate_usd],
                ].map(([label, value]) => (
                  <div key={String(label)} className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-3">
                    <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">{label}</p>
                    <p className="mt-1 text-lg font-semibold tabular-nums text-[var(--navy-100)]">${Number(value).toFixed(2)}</p>
                  </div>
                ))}
              </div>
              <div className="mt-5 divide-y divide-[var(--border)]">
                {data.costs.items.map((item) => (
                  <div key={item.id} className="flex items-start justify-between gap-4 py-3 first:pt-0">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[var(--navy-200)]">{item.name}</p>
                      <p className="mt-0.5 text-xs text-[var(--muted)]">{item.provider}</p>
                      {item.resource_id && (
                        <p className="mt-1 break-all font-mono text-[10px] text-[var(--muted)]">
                          {item.resource_id}
                        </p>
                      )}
                    </div>
                    <p className={`shrink-0 text-sm font-semibold tabular-nums ${item.configured ? "text-[var(--navy-100)]" : "text-amber-300"}`}>{item.configured ? `$${(item.monthly_estimate_usd ?? 0).toFixed(2)}` : "Not configured"}</p>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-xs leading-5 text-[var(--muted)]">{data.costs.detail}</p>
              <CostHistoryChart points={data.costs.history ?? []} />
            </article>
          </section>
        </div>
      ) : null}
    </AdminShell>
  );
}
