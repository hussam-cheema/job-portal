import { Suspense } from "react";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import { fetchDirectoryPage, fetchDirectoryPages, fetchFilters, fetchJobs } from "@/lib/api";
import type { JobListResponse } from "@/lib/types";
import { JobCard } from "@/components/JobCard";
import { JobFilters } from "@/components/JobFilters";
import { Pagination } from "@/components/Pagination";
import {
  directoryPageMetadata,
  normalizeDirectoryTitle,
} from "@/lib/directoryPageMetadata";
import { wrapRichTextTables } from "@/lib/richText";

export const dynamic = "force-dynamic";
export const revalidate = 0;

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
  return directoryPageMetadata("category", category);
}

export default async function CategoryPage({ params, searchParams }: Props) {
  const { category: raw } = await params;
  const values = await searchParams;
  const [filters, cmsPage, directoryPages] = await Promise.all([
    fetchFilters(),
    fetchDirectoryPage("category", raw),
    fetchDirectoryPages(),
  ]);
  if (!cmsPage?.taxonomy_value) notFound();
  if (cmsPage.slug !== raw) permanentRedirect(`/categories/${cmsPage.slug}`);
  const category = cmsPage.taxonomy_value;
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
  if (page > 1 && (!data.pages || page > data.pages)) {
    permanentRedirect(basePath);
  }

  return (
    <div className="site-wrap py-10">
      <Link href="/" className="mb-6 inline-flex text-sm text-[var(--muted)] hover:text-[var(--navy-200)]">
        ← All jobs
      </Link>
      <section className="mb-8">
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--accent)]">
          Category
        </p>
        <h1 className="text-3xl font-semibold text-[var(--navy-100)]">
          {normalizeDirectoryTitle(cmsPage.title)}
        </h1>
        {cmsPage.content && (
          <div
            className="prose-job mt-4 max-w-3xl text-[var(--navy-200)]"
            dangerouslySetInnerHTML={{ __html: wrapRichTextTables(cmsPage.content) }}
          />
        )}
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
            {data.items.map((job) => <JobCard key={job.id} job={job} directoryPages={directoryPages} />)}
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
