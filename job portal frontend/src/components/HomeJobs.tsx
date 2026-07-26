"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { fetchJobs } from "@/lib/api";
import type {
  Branding,
  FiltersResponse,
  JobListResponse,
  JobQuery,
  StatsResponse,
} from "@/lib/types";
import { JobCard } from "@/components/JobCard";
import { JobFilters } from "@/components/JobFilters";
import { JobStats } from "@/components/JobStats";
import { Pagination } from "@/components/Pagination";
import { SubscriptionForm } from "@/components/SubscriptionForm";

type Props = {
  initialJobs: JobListResponse;
  filters: FiltersResponse;
  stats: StatsResponse;
  branding: Branding;
};

export function HomeJobs({ initialJobs, filters, stats, branding }: Props) {
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const query = useMemo<JobQuery>(() => {
    const params = new URLSearchParams(queryString);
    const value = (key: string) => params.get(key) || undefined;
    return {
      q: value("q"),
      sector: value("sector"),
      category: value("category"),
      city: value("city"),
      province: value("province"),
      date: value("date") || value("date_from"),
      page: Math.max(1, Number(value("page") || 1) || 1),
      page_size: 30,
    };
  }, [queryString]);
  const [data, setData] = useState(initialJobs);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!queryString) {
      setData(initialJobs);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void fetchJobs(query)
      .then((response) => {
        if (!cancelled) setData(response);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [initialJobs, query, queryString]);

  return (
    <div className="site-wrap py-10">
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
        <JobFilters filters={filters} />
      </section>

      <section className={`card-panel transition-opacity ${loading ? "opacity-60" : ""}`}>
        <div className="px-4 sm:px-5 py-3.5 border-b border-[var(--border)] flex items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-[var(--navy-100)]">Latest jobs</h2>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              Newest first · 30 per page · hover to expand
            </p>
          </div>
          <span className="font-mono text-xs text-[var(--navy-400)] tabular-nums">
            {loading ? "Loading…" : `${data.total} roles`}
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
          <div className="job-list" aria-busy={loading}>
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
