"use client";

import Link from "next/link";
import { useState } from "react";
import type { DirectoryPageLink, JobSummary } from "@/lib/types";
import { toSeoSlug } from "@/lib/slug";
import {
  decodeHtmlEntities,
  formatDateShort,
  formatSalary,
  isDeadlinePast,
  labelSource,
  sourceBadgeClass,
  stripHtml,
  tagColorClass,
} from "@/lib/format";
import { findDirectoryPage, publicPagePath } from "@/lib/pagePath";

type Props = {
  job: JobSummary;
  homepageOverview?: boolean;
  directoryPages?: DirectoryPageLink[];
};

export function JobCard({ job, homepageOverview = false, directoryPages = [] }: Props) {
  const [open, setOpen] = useState(false);
  const salary =
    job.salary_range ||
    formatSalary(job.salary_min, job.salary_max, job.currency, job.salary_range);
  const displaySalary = decodeHtmlEntities(salary);
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
  const jobHref = `/jobs/${job.slug || job.id}`;
  const publishedValue = job.published_date || job.created_at;
  const deadlineValue = job.deadline_date || job.application_deadline;
  const fullDescription =
    stripHtml(job.description) || "No description is available for this listing yet.";
  const newspaper = job.newspaper?.trim();
  const educationRequired = job.education_required?.trim();
  const experienceRequired = job.experience_required?.trim();
  const hasHomepageOverview = Boolean(
    newspaper || educationRequired || experienceRequired || deadlineValue
  );
  const categoryPage = findDirectoryPage(directoryPages, "category", job.category);

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
          <time
            dateTime={publishedValue || undefined}
            className="font-mono text-xs text-[var(--navy-400)]"
          >
            {date}
          </time>
        </div>

        <div className="min-w-0 flex-1">
          <h2 className="text-[1.05rem] sm:text-[1.08rem] font-semibold text-[var(--navy-100)] leading-snug tracking-tight">
            <Link
              href={jobHref}
              className="hover:text-[var(--accent)] transition-colors"
            >
              {decodeHtmlEntities(job.title)}
            </Link>
          </h2>
          {applicationsClosed && (
            <span className="mt-2 inline-flex rounded-full border border-red-500 bg-red-500/10 px-3 py-1 text-xs font-bold uppercase tracking-wide text-red-500">
              Applications Closed
            </span>
          )}
          <p className="mt-1 text-sm text-[var(--muted)]">
            {decodeHtmlEntities(job.company || job.source || "Unknown employer")}
            {job.nationwide
              ? " · Pakistan"
              : job.location
                ? ` · ${decodeHtmlEntities(job.location)}`
                : job.city
                  ? ` · ${decodeHtmlEntities(job.city)}`
                  : ""}
            {displaySalary ? ` · ${displaySalary}` : ""}
          </p>

          <div className="mt-2.5 flex flex-wrap gap-1.5 relative z-10">
            <span className={`tag ${sourceBadgeClass(job.source_type || job.job_type || "")}`}>
              {labelSource(job.source_type || job.job_type || "private")}
            </span>
            {job.category && categoryPage ? (
              <Link
                href={publicPagePath(categoryPage)}
                className={`tag job-tag-link ${tagColorClass(job.category)} hover:brightness-110`}
              >
                {decodeHtmlEntities(job.category)}
              </Link>
            ) : job.category ? (
              <span className={`tag ${tagColorClass(job.category)}`}>
                {decodeHtmlEntities(job.category)}
              </span>
            ) : null}
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
                  {decodeHtmlEntities(t)}
                </Link>
              ))}
          </div>

          {homepageOverview ? (
            hasHomepageOverview && (
              <div className={`job-card-expand ${open ? "job-card-expand-visible" : ""}`}>
                <div className="job-card-overview-details mt-3 text-xs text-[var(--muted)]">
                  {newspaper && (
                    <div className="job-card-overview-detail">
                      <span className="font-semibold text-[var(--navy-200)]">Newspaper:</span>{" "}
                      {decodeHtmlEntities(newspaper)}
                    </div>
                  )}
                  {educationRequired && (
                    <div className="job-card-overview-detail">
                      <span className="font-semibold text-[var(--navy-200)]">Required Education:</span>{" "}
                      {decodeHtmlEntities(educationRequired)}
                    </div>
                  )}
                  {experienceRequired && (
                    <div className="job-card-overview-detail">
                      <span className="font-semibold text-[var(--navy-200)]">Required Experience:</span>{" "}
                      {decodeHtmlEntities(experienceRequired)}
                    </div>
                  )}
                  {deadlineValue && (
                    <div className="job-card-overview-detail font-bold text-red-500">
                      Deadline: <time dateTime={deadlineValue}>{formatDateShort(deadlineValue)}</time>
                    </div>
                  )}
                </div>
              </div>
            )
          ) : (
            <div className={`job-card-expand ${open ? "job-card-expand-visible" : ""}`}>
              <p className="job-card-overview-description mt-3 text-sm leading-relaxed text-[var(--navy-200)]">
                {fullDescription}
              </p>
              <div className="job-card-overview-details mt-3 text-xs text-[var(--muted)]">
                {deadlineValue && (
                  <div className="job-card-overview-detail font-bold text-red-500">
                    Deadline: <time dateTime={deadlineValue}>{formatDateShort(deadlineValue)}</time>
                  </div>
                )}
                {educationRequired && (
                  <div className="job-card-overview-detail">
                    <span className="font-semibold text-[var(--navy-200)]">Required Education:</span>{" "}
                    {decodeHtmlEntities(educationRequired)}
                  </div>
                )}
                {experienceRequired && (
                  <div className="job-card-overview-detail">
                    <span className="font-semibold text-[var(--navy-200)]">Required Experience:</span>{" "}
                    {decodeHtmlEntities(experienceRequired)}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <Link
        href={jobHref}
        className="job-card-more"
        title="Full job details and commonly asked Q&A"
      >
        More →
      </Link>
    </article>
  );
}
