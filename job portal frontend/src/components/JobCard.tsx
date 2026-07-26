"use client";

import Link from "next/link";
import { useState } from "react";
import type { JobSummary } from "@/lib/types";
import { toSeoSlug } from "@/lib/slug";
import {
  formatDateShort,
  formatSalary,
  isDeadlinePast,
  labelSource,
  sourceBadgeClass,
  summarize,
  tagColorClass,
} from "@/lib/format";

type Props = {
  job: JobSummary;
};

export function JobCard({ job }: Props) {
  const [open, setOpen] = useState(false);
  const salary =
    job.salary_range ||
    formatSalary(job.salary_min, job.salary_max, job.currency, job.salary_range);
  const date = formatDateShort(job.published_date || job.created_at);
  const applicationsClosed =
    job.applications_closed || isDeadlinePast(job.deadline_date || job.application_deadline);
  const locationTags = job.nationwide
    ? ["Pakistan"]
    : [...(job.provinces || []), ...(job.cities || [])];
  const tags = Array.from(
    new Set(
      [
        ...(job.tags || []),
        ...locationTags,
        ...(!job.tags?.length ? [labelSource(job.source_type), job.category] : []),
      ].filter(Boolean) as string[]
    )
  );

  return (
    <article
      className={`job-card ${open ? "job-card-open" : ""}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setOpen(false);
      }}
    >
      <div className="job-card-main">
        <div className="job-card-date">
          <span className="font-mono text-xs text-[var(--navy-400)]">{date}</span>
        </div>

        <div className="min-w-0 flex-1">
          <h2 className="text-[1.05rem] sm:text-[1.08rem] font-semibold text-[var(--navy-100)] leading-snug tracking-tight">
            <Link
              href={`/jobs/${job.slug || job.id}`}
              className="hover:text-[var(--accent)] transition-colors"
            >
              {job.title}
            </Link>
          </h2>
          {applicationsClosed && (
            <span className="mt-2 inline-flex rounded-full border border-red-500 bg-red-500/10 px-3 py-1 text-xs font-bold uppercase tracking-wide text-red-500">
              Applications Closed
            </span>
          )}
          <p className="mt-1 text-sm text-[var(--muted)]">
            {job.company || job.source || "Unknown employer"}
            {job.nationwide ? " · Pakistan" : job.location ? ` · ${job.location}` : job.city ? ` · ${job.city}` : ""}
            {salary ? ` · ${salary}` : ""}
          </p>

          <div className="mt-2.5 flex flex-wrap gap-1.5 relative z-10">
            <span className={`tag ${sourceBadgeClass(job.source_type || job.job_type || "")}`}>
              {labelSource(job.source_type || job.job_type || "private")}
            </span>
            {job.category && (
              <Link
                href={`/categories/${toSeoSlug(job.category)}`}
                className={`tag job-tag-link ${tagColorClass(job.category)} hover:brightness-110`}
              >
                {job.category}
              </Link>
            )}
            {tags
              .filter(
                (t) =>
                  t.toLowerCase() !==
                    labelSource(job.source_type || job.job_type || "").toLowerCase() &&
                  t.toLowerCase() !== (job.category || "").toLowerCase()
              )
              .slice(0, 8)
              .map((t) => (
                <Link
                  key={t}
                  href={`/tags/${toSeoSlug(t)}`}
                  className={`tag job-tag-link ${tagColorClass(t)} hover:brightness-110`}
                  onClick={(e) => e.stopPropagation()}
                  onMouseDown={(e) => e.stopPropagation()}
                >
                  {t}
                </Link>
              ))}
          </div>

          <div className={`job-card-expand ${open ? "job-card-expand-visible" : ""}`}>
            <p className="text-sm text-[var(--navy-200)] leading-relaxed mt-3">
              {summarize(job.description, 320)}
            </p>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--muted)]">
              {job.experience_required && <span>Exp: {job.experience_required}</span>}
              {job.education_required && <span>Edu: {job.education_required}</span>}
              {(job.deadline_date || job.application_deadline) && (
                <span className="font-bold text-red-500">
                  Deadline: {formatDateShort(job.deadline_date || job.application_deadline)}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      <Link
        href={`/jobs/${job.slug || job.id}`}
        className="job-card-more"
        title="Full job details and commonly asked Q&A"
      >
        More →
      </Link>
    </article>
  );
}
