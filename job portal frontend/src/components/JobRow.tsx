import Link from "next/link";
import type { JobSummary } from "@/lib/types";
import {
  formatDate,
  formatSalary,
  labelSource,
  sourceBadgeClass,
} from "@/lib/format";

type Props = {
  job: JobSummary;
  index: number;
};

export function JobRow({ job, index }: Props) {
  const salary = formatSalary(job.salary_min, job.salary_max, job.currency);
  const date = formatDate(job.published_date || job.created_at);
  const issueNo = String(index).padStart(3, "0");

  return (
    <Link href={`/jobs/${job.id}`} className="job-row group">
      <div className="pt-0.5">
        <div className="font-mono text-xs text-[var(--navy-400)] tabular-nums">
          #{issueNo}
        </div>
        <div className="mt-1 text-[11px] text-[var(--muted)] leading-tight">
          {date}
        </div>
      </div>

      <div className="min-w-0">
        <h2 className="text-[0.98rem] sm:text-base font-semibold text-[var(--navy-100)] group-hover:text-white transition-colors leading-snug">
          {job.title}
        </h2>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-[var(--muted)]">
          {job.company && (
            <span className="text-[var(--navy-300)]">{job.company}</span>
          )}
          {job.location && (
            <>
              <span className="text-[var(--navy-600)]">·</span>
              <span>{job.location}</span>
            </>
          )}
          {job.experience_required && (
            <>
              <span className="text-[var(--navy-600)]">·</span>
              <span>{job.experience_required}</span>
            </>
          )}
        </div>
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          <span className={`badge ${sourceBadgeClass(job.source_type)}`}>
            {labelSource(job.source_type)}
          </span>
          {job.category && (
            <span className="badge badge-muted">{job.category}</span>
          )}
          {job.skills?.slice(0, 3).map((s) => (
            <span key={s} className="badge badge-muted normal-case tracking-normal font-medium">
              {s}
            </span>
          ))}
        </div>
      </div>

      <div className="job-row-meta hidden sm:flex flex-col items-end gap-1.5 text-right shrink-0 pt-0.5">
        {salary && (
          <span className="text-sm font-medium text-[var(--navy-200)] tabular-nums">
            {salary}
          </span>
        )}
        {job.application_deadline && (
          <span className="text-[11px] text-[var(--muted)]">
            Due {formatDate(job.application_deadline)}
          </span>
        )}
        <span className="text-[var(--navy-500)] group-hover:text-[var(--accent)] transition-colors text-sm mt-1">
          Read →
        </span>
      </div>
    </Link>
  );
}
