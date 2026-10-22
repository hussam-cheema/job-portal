import Link from "next/link";
import type { StatsResponse } from "@/lib/types";

export function JobStats({ stats }: { stats: StatsResponse }) {
  const openForApply = stats.open_for_apply ?? 0;
  const archivedJobs =
    stats.archived_jobs ?? Math.max(stats.total_jobs - openForApply, 0);
  const activeGovernment = stats.active_government_jobs ?? 0;
  const activePrivate = stats.active_private_jobs ?? 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      <StatCard label="Total active jobs" value={openForApply} href="/" accent />
      <StatCard label="Government jobs" value={activeGovernment} href="/?sector=govt" />
      <StatCard label="Private jobs" value={activePrivate} href="/?sector=private" />
      <StatCard label="Archived jobs" value={archivedJobs} href="/archive" />
    </div>
  );
}

function StatCard({
  label,
  value,
  href,
  accent,
}: {
  label: string;
  value: number;
  href: string;
  accent?: boolean;
}) {
  return (
    <Link href={href} className="stat-card block transition hover:border-[var(--blue)] hover:bg-[var(--blue-soft)]">
      <div
        className={`text-2xl font-semibold tabular-nums tracking-tight ${
          accent ? "text-[var(--accent)]" : "text-[var(--navy-100)]"
        }`}
      >
        {value.toLocaleString()}
      </div>
      <div className="mt-1 text-xs uppercase tracking-wider text-[var(--muted)]">{label}</div>
    </Link>
  );
}
