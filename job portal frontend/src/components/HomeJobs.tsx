import { Suspense } from "react";
import type {
  Branding,
  FiltersResponse,
  JobListResponse,
  JobQuery,
  StatsResponse,
} from "@/lib/types";
import { stripHtml } from "@/lib/format";
import { canonicalSiteUrl } from "@/lib/siteUrl";
import { JobCard } from "@/components/JobCard";
import { JobFilters } from "@/components/JobFilters";
import { JobStats } from "@/components/JobStats";
import { Pagination } from "@/components/Pagination";
import { SubscriptionForm } from "@/components/SubscriptionForm";

type Props = {
  initialJobs: JobListResponse;
  initialQuery: JobQuery;
  filters: FiltersResponse;
  stats: StatsResponse;
  branding: Branding;
};

export function HomeJobs({ initialJobs, initialQuery: query, filters, stats, branding }: Props) {
  const data = initialJobs;
  const siteUrl = canonicalSiteUrl();
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    numberOfItems: data.items.length,
    itemListElement: data.items.map((job, index) => ({
      "@type": "ListItem",
      position: index + 1,
      url: `${siteUrl}/jobs/${job.slug || job.id}`,
      item: {
        "@type": "JobPosting",
        title: job.title,
        description: stripHtml(job.description || ""),
        datePosted: job.published_date || job.created_at || undefined,
        validThrough: job.deadline_date || job.application_deadline || undefined,
        employmentType: job.employment_type || job.job_type || undefined,
        industry: job.category || undefined,
        skills: (job.skills || []).join(", ") || undefined,
        hiringOrganization: {
          "@type": "Organization",
          name: job.company || job.source || "Pakistan Jobs Market",
        },
        jobLocation: [...(job.cities || []), ...(job.provinces || [])].map((location) => ({
          "@type": "Place",
          address: {
            "@type": "PostalAddress",
            addressLocality: location,
            addressCountry: "PK",
          },
        })),
        url: `${siteUrl}/jobs/${job.slug || job.id}`,
      },
    })),
  };

  return (
    <div className="site-wrap py-10">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(structuredData).replace(/</g, "\\u003c"),
        }}
      />
      <section className="mb-8 text-center">
        <h1 className="mx-auto max-w-3xl text-3xl sm:text-4xl font-semibold tracking-tight text-[var(--navy-100)] leading-[1.15]">
          {branding.site_header}
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-[var(--muted)] text-base leading-relaxed">
          {branding.site_description}
        </p>
      </section>

      <section className="mb-6">
        <JobStats stats={stats} />
      </section>

      <div className="mb-6">
        <SubscriptionForm />
      </div>

      <section className="mb-6">
        <Suspense fallback={<div className="h-20 animate-pulse rounded-xl bg-[var(--card)]" />}>
          <JobFilters filters={filters} />
        </Suspense>
      </section>

      <section className="card-panel transition-opacity">
        <div className="px-4 sm:px-5 py-3.5 border-b border-[var(--border)] flex items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-[var(--navy-100)]">Latest jobs</h2>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              Newest first · 30 per page · hover to expand
            </p>
          </div>
          <span className="font-mono text-xs text-[var(--navy-400)] tabular-nums">
            {data.total} roles
          </span>
        </div>

        {data.items.length === 0 ? (
          <div className="px-5 py-14 text-center">
            <p className="text-[var(--navy-200)] font-medium text-lg">No openings yet</p>
            <p className="mt-2 text-sm text-[var(--muted)] max-w-md mx-auto">
              Try clearing filters or check back later for new openings.
            </p>
          </div>
        ) : (
          <div className="job-list">
            {data.items.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </div>
        )}

        <Pagination
          page={data.page}
          pages={data.pages}
          total={data.total}
          query={{
            q: query.q,
            sector: query.sector,
            category: query.category,
            city: query.city,
            province: query.province,
            date: query.date,
          }}
        />
      </section>
    </div>
  );
}
