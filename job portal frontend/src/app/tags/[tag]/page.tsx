import { Suspense } from "react";
import Link from "next/link";
import { permanentRedirect } from "next/navigation";
import { fetchFilters, fetchJobs } from "@/lib/api";
import type { JobListResponse } from "@/lib/types";
import { JobCard } from "@/components/JobCard";
import { JobFilters } from "@/components/JobFilters";
import { Pagination } from "@/components/Pagination";
import { labelFromSlug, toSeoSlug } from "@/lib/slug";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Props = {
  params: Promise<{ tag: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function pick(sp: Record<string, string | string[] | undefined>, key: string) {
  const v = sp[key];
  return typeof v === "string" ? v : undefined;
}

export async function generateMetadata({ params }: Props) {
  const { tag } = await params;
  const filters = await fetchFilters();
  const label =
    filters.tags.find((item) => toSeoSlug(item) === tag) || labelFromSlug(tag);
  const indexableJobs = await fetchJobs({
    tag: label,
    indexable_only: true,
    page_size: 1,
  });
  return {
    title: { absolute: `${label} Jobs in Pakistan | Pakistan Jobs Market` },
    description: `Browse Pakistan job openings tagged ${label}.`,
    alternates: { canonical: `/tags/${tag}` },
    robots: { index: indexableJobs.total > 0, follow: true },
  };
}

export default async function TagPage({ params, searchParams }: Props) {
  const { tag: raw } = await params;
  const filters = await fetchFilters();
  const tag = filters.tags.find((item) => toSeoSlug(item) === raw) || labelFromSlug(raw);
  const sp = await searchParams;
  const q = pick(sp, "q");
  const sector = pick(sp, "sector");
  const category = pick(sp, "category");
  const city = pick(sp, "city");
  const date = pick(sp, "date") || pick(sp, "date_from");
  const page = Math.max(1, Number(pick(sp, "page") || 1) || 1);
  const basePath = `/tags/${raw}`;

  const data: JobListResponse = await fetchJobs({
      tag,
      q,
      sector,
      category,
      city,
      date,
      open_only: true,
      page,
      page_size: 30,
    });
  if (page > 1 && (!data.pages || page > data.pages)) {
    permanentRedirect(basePath);
  }

  return (
    <div className="site-wrap py-10">
      <Link
        href="/"
        className="inline-flex text-sm text-[var(--muted)] hover:text-[var(--navy-200)] mb-6 transition-colors"
      >
        ← All jobs
      </Link>

      <section className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--accent)] mb-2">
          Tag
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-white">{tag}</h1>
        <p className="mt-2 text-[var(--muted)]">
          {data.total} related opening{data.total === 1 ? "" : "s"}
        </p>
      </section>

      <section className="mb-6">
        <Suspense fallback={<div className="h-20 animate-pulse rounded-xl bg-[var(--card)]" />}>
          <JobFilters filters={filters} basePath={basePath} />
        </Suspense>
      </section>

      <section className="card-panel">
        {data.items.length === 0 ? (
          <div className="px-5 py-14 text-center text-[var(--muted)]">
            No jobs for this tag yet.
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
          basePath={basePath}
        />
      </section>
    </div>
  );
}
