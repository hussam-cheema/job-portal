import { Suspense } from "react";
import { fetchFilters, fetchJobs, fetchStats } from "@/lib/api";
import type { FiltersResponse, JobListResponse, StatsResponse } from "@/lib/types";
import { JobCard } from "@/components/JobCard";
import { JobFilters } from "@/components/JobFilters";
import { JobStats } from "@/components/JobStats";
import { Pagination } from "@/components/Pagination";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function pick(sp: Record<string, string | string[] | undefined>, key: string) {
  const v = sp[key];
  return typeof v === "string" ? v : undefined;
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;
  const q = pick(sp, "q");
  const sector = pick(sp, "sector");
  const category = pick(sp, "category");
  const city = pick(sp, "city");
  const date = pick(sp, "date") || pick(sp, "date_from");
  const page = Math.max(1, Number(pick(sp, "page") || 1) || 1);

  const [data, filters, stats]: [JobListResponse, FiltersResponse, StatsResponse] =
    await Promise.all([
      fetchJobs({
        q,
        sector,
        category,
        city,
        date,
        page,
        page_size: 30,
      }),
      fetchFilters(),
      fetchStats(),
    ]);

  return (
    <div className="site-wrap py-10">
      <section className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--accent)] mb-3">
          Pakistan jobs
        </p>
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-[var(--navy-100)] max-w-3xl leading-[1.15]">
          Latest government & private job openings in Pakistan
        </h1>
        <p className="mt-4 text-[var(--muted)] max-w-2xl text-base leading-relaxed">
          Hover a job for a summary, then open the full page for complete details and available interview Q&amp;A.
        </p>
      </section>

      <section className="mb-6">
        <JobStats stats={stats} />
      </section>

      <section className="mb-6">
        <Suspense fallback={<div className="h-24 animate-pulse rounded-xl bg-[var(--card)]" />}>
          <JobFilters filters={filters} />
        </Suspense>
      </section>

      <section className="card-panel">
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
          query={{ q, sector, category, city, date }}
        />
      </section>
    </div>
  );
}
