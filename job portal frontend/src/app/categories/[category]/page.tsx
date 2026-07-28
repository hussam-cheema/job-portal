import { Suspense } from "react";
import Link from "next/link";
import { fetchFilters, fetchJobs } from "@/lib/api";
import type { JobListResponse } from "@/lib/types";
import { JobCard } from "@/components/JobCard";
import { JobFilters } from "@/components/JobFilters";
import { Pagination } from "@/components/Pagination";
import { labelFromSlug, toSeoSlug } from "@/lib/slug";

type Props = {
  params: Promise<{ category: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function pick(values: Record<string, string | string[] | undefined>, key: string) {
  const value = values[key];
  return typeof value === "string" ? value : undefined;
}

export async function generateMetadata({ params }: Props) {
  const { category } = await params;
  const label = labelFromSlug(category);
  return {
    title: `${label} jobs in Pakistan`,
    description: `Browse current ${label} job openings across Pakistan.`,
    alternates: { canonical: `/categories/${category}` },
    robots: { index: true, follow: true },
  };
}

export default async function CategoryPage({ params, searchParams }: Props) {
  const { category: raw } = await params;
  const values = await searchParams;
  const filters = await fetchFilters();
  const category =
    filters.categories.find((item) => toSeoSlug(item) === raw) || labelFromSlug(raw);
  const q = pick(values, "q");
  const sector = pick(values, "sector");
  const city = pick(values, "city");
  const date = pick(values, "date") || pick(values, "date_from");
  const page = Math.max(1, Number(pick(values, "page") || 1) || 1);
  const basePath = `/categories/${raw}`;
  const data: JobListResponse = await fetchJobs({
    q,
    sector,
    category,
    city,
    date,
    page,
    page_size: 30,
  });

  return (
    <div className="site-wrap py-10">
      <Link href="/" className="mb-6 inline-flex text-sm text-[var(--muted)] hover:text-[var(--navy-200)]">
        ← All jobs
      </Link>
      <section className="mb-8">
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">
          Category
        </p>
        <h1 className="text-3xl font-semibold text-[var(--navy-100)]">{category}</h1>
        <p className="mt-2 text-[var(--muted)]">
          {data.total} related opening{data.total === 1 ? "" : "s"}
        </p>
      </section>
      <section className="mb-6">
        <Suspense fallback={<div className="h-20 animate-pulse rounded-lg bg-[var(--card)]" />}>
          <JobFilters filters={filters} basePath={basePath} />
        </Suspense>
      </section>
      <section className="card-panel">
        {data.items.length === 0 ? (
          <div className="px-5 py-14 text-center text-[var(--muted)]">No jobs in this category yet.</div>
        ) : (
          <div className="job-list">
            {data.items.map((job) => <JobCard key={job.id} job={job} />)}
          </div>
        )}
        <Pagination
          page={data.page}
          pages={data.pages}
          total={data.total}
          query={{ q, sector, city, date }}
          basePath={basePath}
        />
      </section>
    </div>
  );
}
