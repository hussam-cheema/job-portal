"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { AdminShell } from "@/components/AdminShell";
import { useAdminAuth } from "@/lib/adminAuth";
import { adminInfrastructure } from "@/lib/api";
import type {
  InfrastructureComputeMetric,
  InfrastructureDashboard,
  InfrastructureStorageMetric,
} from "@/lib/types";

type CostDriver = InfrastructureDashboard["cost_drivers"][number];
type ProviderBilling = InfrastructureDashboard["provider_billing"][number];

const statusStyles: Record<string, string> = {
  healthy: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  managed: "border-blue-400/25 bg-blue-400/10 text-blue-300",
  warning: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  critical: "border-red-400/25 bg-red-400/10 text-red-300",
  unavailable: "border-slate-400/25 bg-slate-400/10 text-slate-300",
  unknown: "border-slate-400/25 bg-slate-400/10 text-slate-300",
  info: "border-blue-400/25 bg-blue-400/10 text-blue-300",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${statusStyles[status] || statusStyles.unknown}`}
    >
      {status}
    </span>
  );
}

function Progress({ value, color = "var(--accent)" }: { value: number | null; color?: string }) {
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-[var(--navy-800)]">
      <div
        className="h-full rounded-full transition-[width] duration-500"
        style={{
          width: `${Math.min(100, Math.max(0, value ?? 0))}%`,
          backgroundColor: color,
        }}
      />
    </div>
  );
}

function Gauge({ value, color = "var(--accent)" }: { value: number | null; color?: string }) {
  const normalized = Math.min(100, Math.max(0, value ?? 0));
  return (
    <div
      className="relative h-24 w-24 shrink-0"
      role="img"
      aria-label={value === null ? "Usage unavailable" : `${value.toFixed(1)} percent used`}
    >
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

function formatBytes(value: number | null) {
  if (value === null) return "Unavailable";
  if (value === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const amount = value / 1024 ** index;
  return `${amount.toFixed(index > 2 ? 2 : index > 0 ? 1 : 0)} ${units[index]}`;
}

function formatNumber(value: number) {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatDriverValue(value: number | null, unit: string) {
  if (value === null) return "Not reported";
  if (unit === "USD") return `$${value.toFixed(2)}`;
  return `${formatNumber(value)} ${unit}`;
}

function ProviderSection({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section data-testid="infrastructure-section" className="card-panel overflow-hidden">
      <header className="border-b border-[var(--border)] px-5 py-5 sm:px-6">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">{eyebrow}</p>
        <h3 className="mt-1 text-lg font-semibold text-[var(--navy-100)]">{title}</h3>
        <p className="mt-1 max-w-4xl text-xs leading-5 text-[var(--muted)]">{description}</p>
      </header>
      <div className="p-5 sm:p-6">{children}</div>
    </section>
  );
}

function StorageCard({ metric, title }: { metric?: InfrastructureStorageMetric; title: string }) {
  if (!metric) {
    return (
      <article className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-4">
        <p className="text-sm font-medium text-[var(--navy-200)]">{title}</p>
        <p className="mt-4 text-xl font-semibold text-[var(--navy-100)]">Unavailable</p>
      </article>
    );
  }

  const color =
    metric.status === "critical"
      ? "var(--danger)"
      : metric.status === "warning"
        ? "var(--gold)"
        : "var(--accent)";

  return (
    <article className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--navy-200)]">{title}</p>
          <p className="mt-0.5 text-[10px] uppercase tracking-wider text-[var(--muted)]">Live capacity</p>
        </div>
        <StatusBadge status={metric.status} />
      </div>
      <div className="mt-5 flex items-center gap-4">
        <Gauge value={metric.utilization_percent} color={color} />
        <div className="min-w-0">
          <p className="text-2xl font-semibold tabular-nums text-[var(--navy-100)]">
            {formatBytes(metric.used_bytes)}
          </p>
          <p className="mt-1 text-xs text-[var(--muted)]">of {formatBytes(metric.total_bytes)} tracked</p>
          {metric.object_count !== null && (
            <p className="mt-2 text-xs text-[var(--navy-300)]">
              {metric.object_count.toLocaleString()} objects
            </p>
          )}
        </div>
      </div>
      <div className="mt-4">
        <Progress value={metric.utilization_percent} color={color} />
      </div>
    </article>
  );
}

function UsageCard({ driver, emptyLabel }: { driver?: CostDriver; emptyLabel: string }) {
  if (!driver) {
    return (
      <article className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-4">
        <p className="text-sm font-medium text-[var(--navy-200)]">{emptyLabel}</p>
        <p className="mt-4 text-xl font-semibold text-[var(--navy-100)]">Not reported</p>
      </article>
    );
  }

  const hasQuota = driver.included !== null;
  return (
    <article className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--navy-200)]">{driver.metric}</p>
          <p className="mt-0.5 text-[10px] uppercase tracking-wider text-[var(--muted)]">{driver.plan}</p>
        </div>
        <StatusBadge status={driver.status} />
      </div>
      <p className="mt-4 text-xl font-semibold tabular-nums text-[var(--navy-100)]">
        {hasQuota && driver.used !== null
          ? `${formatNumber(driver.used)} / ${formatNumber(driver.included as number)}`
          : formatDriverValue(driver.used, driver.unit)}
      </p>
      {hasQuota && (
        <>
          <p className="mt-1 text-xs text-[var(--muted)]">
            {driver.unit} used out of total quota
          </p>
          <div className="mt-3">
            <Progress value={driver.utilization_percent} />
          </div>
          <p className="mt-2 text-xs text-[var(--muted)]">
            {driver.remaining === null
              ? "Remaining quota unavailable"
              : `${formatNumber(driver.remaining)} ${driver.unit} remaining`}
          </p>
        </>
      )}
      <p className="mt-4 text-xs leading-5 text-[var(--muted)]">{driver.detail}</p>
      <p className="mt-2 text-[10px] text-[var(--muted)]">Source: {driver.source}</p>
    </article>
  );
}

function LivePercentCard({
  title,
  value,
  detail,
  color,
}: {
  title: string;
  value: number | null;
  detail: string;
  color?: string;
}) {
  return (
    <article className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-4 sm:p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">{title}</p>
          <p className="mt-3 text-2xl font-semibold tabular-nums text-[var(--navy-100)]">
            {value === null ? "Unavailable" : `${value.toFixed(1)}%`}
          </p>
          <p className="mt-1 text-xs text-[var(--muted)]">{detail}</p>
        </div>
        <Gauge value={value} color={color} />
      </div>
    </article>
  );
}

function FinOpsCard({ label, billing }: { label: string; billing?: ProviderBilling }) {
  const billed = billing?.current_amount_due_usd;
  const grossUsage = billing?.current_usage_usd;
  const hasCredit =
    typeof billed === "number" &&
    typeof grossUsage === "number" &&
    Math.abs(grossUsage - billed) >= 0.005;

  return (
    <article className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--navy-200)]">{label}</p>
          <p className="mt-0.5 text-[10px] uppercase tracking-wider text-[var(--muted)]">
            Current month so far
          </p>
        </div>
        {billing && <StatusBadge status={billing.status} />}
      </div>
      <p className="mt-5 text-2xl font-semibold tabular-nums text-[var(--navy-100)]">
        {!billing || !billing.configured ? "Unavailable" : `$${billed?.toFixed(2) ?? "0.00"}`}
      </p>
      {hasCredit && typeof grossUsage === "number" && (
        <p className="mt-1 text-xs text-[var(--muted)]">
          ${grossUsage.toFixed(2)} gross usage before plan credit
        </p>
      )}
      <p className="mt-4 text-xs leading-5 text-[var(--muted)]">
        {billing?.detail ?? "Billing integration is not configured."}
      </p>
      {billing && <p className="mt-2 text-[10px] text-[var(--muted)]">Source: {billing.source}</p>}
    </article>
  );
}

export default function InfrastructureAnalyticsPage() {
  const { token } = useAdminAuth();
  const [data, setData] = useState<InfrastructureDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (force = false) => {
      if (!token) return;
      setRefreshing(true);
      setError(null);
      try {
        setData(await adminInfrastructure(token, force));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Infrastructure metrics could not be loaded");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [token],
  );

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), 30_000);
    return () => window.clearInterval(interval);
  }, [load]);

  const metrics = useMemo(() => {
    const driver = (id: string) => data?.cost_drivers.find((item) => item.id === id);
    const billing = (id: string) => data?.provider_billing.find((item) => item.id === id);
    return {
      r2Storage: data?.storage.find((item) => item.id === "r2"),
      databaseStorage: data?.storage.find((item) => item.id === "database"),
      backend: data?.compute.find((item) => item.id === "backend"),
      r2ClassA: driver("r2_class_a"),
      r2ClassB: driver("r2_class_b"),
      r2StoredData: driver("r2_storage"),
      neonCompute: driver("neon_compute"),
      neonNetwork: driver("neon_network"),
      neonHistory: driver("neon_history"),
      neonBranches: driver("neon_branches"),
      railwayNetwork: driver("railway_network"),
      railwayCredit: driver("railway_usage_credit"),
      resendMonthly: driver("resend_monthly_emails"),
      resendDaily: driver("resend_daily_emails"),
      azureBilling: billing("azure"),
      r2Billing: billing("r2"),
      neonBilling: billing("neon"),
      railwayBilling: billing("railway"),
      resendBilling: billing("resend"),
    };
  }, [data]);

  const backend = metrics.backend as InfrastructureComputeMetric | undefined;

  return (
    <AdminShell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold text-[var(--navy-100)]">Infrastructure analytics</h2>
            {data && (
              <span
                className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,.7)]"
                aria-label="Live telemetry"
              />
            )}
          </div>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Focused usage and month-to-date billing across the five services that affect this website.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {data && (
            <p className="text-xs text-[var(--muted)]">
              Updated {new Date(data.collected_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </p>
          )}
          <button type="button" className="btn btn-ghost" disabled={refreshing} onClick={() => void load(true)}>
            {refreshing ? "Refreshing…" : "Refresh now"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-5 rounded-xl border border-red-400/25 bg-red-400/10 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading && !data ? (
        <div className="card-panel p-10 text-center text-sm text-[var(--muted)]">
          Collecting infrastructure telemetry…
        </div>
      ) : data ? (
        <div className="space-y-5">
          <ProviderSection
            eyebrow="Cloudflare R2"
            title="Cloudflare R2"
            description="Storage footprint and the request classes that drive R2 billing. R2 internet egress remains free."
          >
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <StorageCard metric={metrics.r2Storage} title="Object storage" />
              <UsageCard driver={metrics.r2StoredData} emptyLabel="Stored data snapshot" />
              <UsageCard driver={metrics.r2ClassA} emptyLabel="Class A operations" />
              <UsageCard driver={metrics.r2ClassB} emptyLabel="Class B operations" />
            </div>
          </ProviderSection>

          <ProviderSection
            eyebrow="Neon Postgres"
            title="Neon Postgres"
            description="Database storage, compute, public network transfer, history, and active branches for the current billing period."
          >
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <StorageCard metric={metrics.databaseStorage} title="Database storage" />
              <UsageCard driver={metrics.neonCompute} emptyLabel="Compute" />
              <UsageCard driver={metrics.neonNetwork} emptyLabel="Public network transfer" />
              <UsageCard driver={metrics.neonHistory} emptyLabel="History data changes" />
              <UsageCard driver={metrics.neonBranches} emptyLabel="Active branches" />
            </div>
          </ProviderSection>

          <ProviderSection
            eyebrow="Railway Serverless"
            title="Railway Serverless"
            description="Live backend utilization, network egress, and the current plan credit consumed by the serverless API."
          >
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <LivePercentCard
                title="CPU utilization"
                value={backend?.cpu_used_percent ?? null}
                detail={backend?.cpu_allocated_cores === null || backend?.cpu_allocated_cores === undefined ? "Allocation unavailable" : `${backend.cpu_allocated_cores} vCPU allocated`}
              />
              <LivePercentCard
                title="Memory utilization"
                value={backend?.memory_used_percent ?? null}
                detail={`${formatBytes(backend?.memory_used_bytes ?? null)} / ${formatBytes(backend?.memory_allocated_bytes ?? null)}`}
                color="var(--success)"
              />
              <UsageCard driver={metrics.railwayNetwork} emptyLabel="Network egress" />
              <UsageCard driver={metrics.railwayCredit} emptyLabel="Resource usage credit" />
            </div>
          </ProviderSection>

          <ProviderSection
            eyebrow="Resend"
            title="Resend"
            description="Daily and monthly recipient quotas. Both limits are shown independently because either one can block email delivery."
          >
            <div className="grid gap-4 md:grid-cols-2">
              <UsageCard driver={metrics.resendMonthly} emptyLabel="Monthly emails" />
              <UsageCard driver={metrics.resendDaily} emptyLabel="Daily emails" />
            </div>
          </ProviderSection>

          <ProviderSection
            eyebrow="FinOps"
            title="FinOps"
            description="Provider-reported amount due for the current month so far. Free-plan usage credits are not presented as money owed."
          >
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
              <FinOpsCard label="Azure — all services" billing={metrics.azureBilling} />
              <FinOpsCard label="Cloudflare R2" billing={metrics.r2Billing} />
              <FinOpsCard label="Neon" billing={metrics.neonBilling} />
              <FinOpsCard label="Railway" billing={metrics.railwayBilling} />
              <FinOpsCard label="Resend" billing={metrics.resendBilling} />
            </div>
          </ProviderSection>
        </div>
      ) : null}
    </AdminShell>
  );
}
