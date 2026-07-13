import type { StatsResponse } from "@/lib/types";

export function StatsStrip({ stats }: { stats: StatsResponse }) {
  const sources = Object.entries(stats.by_source_type);
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <StatCard label="Open roles" value={String(stats.total_jobs)} />
      {sources.slice(0, 3).map(([key, val]) => (
        <StatCard
          key={key}
          label={key}
          value={String(val)}
          subtle
        />
      ))}
    </div>
  );
}

function StatCard({
  label,
  value,
  subtle,
}: {
  label: string;
  value: string;
  subtle?: boolean;
}) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
      <div
        className={`text-2xl font-semibold tabular-nums tracking-tight ${
          subtle ? "text-[var(--navy-200)]" : "text-white"
        }`}
      >
        {value}
      </div>
      <div className="mt-0.5 text-xs uppercase tracking-wider text-[var(--muted)]">
        {label}
      </div>
    </div>
  );
}
