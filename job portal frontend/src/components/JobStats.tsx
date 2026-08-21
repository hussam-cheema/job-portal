import type { StatsResponse } from "@/lib/types";

export function JobStats({ stats }: { stats: StatsResponse }) {
  const bySource = stats.by_source_type || {};
  const govt = bySource.govt || bySource.government || 0;
  const privateCount =
    bySource.private ||
    (bySource.company || 0) + (bySource.newspaper || 0) ||
    0;
  const openForApply = stats.open_for_apply ?? 0;
  const closedJobs = Math.max(stats.total_jobs - openForApply, 0);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
      <StatCard label="Total jobs" value={stats.total_jobs} accent />
      <StatCard label="Open to apply" value={openForApply} />
      <StatCard label="Closed jobs" value={closedJobs} />
      <StatCard label="Govt jobs" value={govt} />
      <StatCard label="Private jobs" value={privateCount} />
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div className="stat-card">
      <div
        className={`text-2xl font-semibold tabular-nums tracking-tight ${
          accent ? "text-[var(--accent)]" : "text-[var(--navy-100)]"
        }`}
      >
        {value.toLocaleString()}
      </div>
      <div className="mt-1 text-xs uppercase tracking-wider text-[var(--muted)]">{label}</div>
    </div>
  );
}
