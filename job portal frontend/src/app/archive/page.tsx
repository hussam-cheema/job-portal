import type { Metadata } from "next";
import { HomeJobs } from "@/components/HomeJobs";
import {
  fetchBranding,
  fetchDirectoryPages,
  fetchFilters,
  fetchJobs,
  fetchStats,
} from "@/lib/api";
import type { JobQuery } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export const metadata: Metadata = {
  title: "Expired Job Archive | Pakistan Jobs Market",
  description:
    "Browse expired historical job advertisements from Pakistan Jobs Market. Archived records remain available for reference and are excluded from active job search.",
  alternates: { canonical: "/archive" },
  robots: { index: true, follow: true },
};

type ArchivePageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function ArchivePage({ searchParams }: ArchivePageProps) {
  const raw = await searchParams;
  const page = Math.max(1, Number(first(raw.page) || 1) || 1);
  const query: JobQuery = {
    q: first(raw.q),
    source_type: first(raw.source_type),
    sector: first(raw.sector),
    category: first(raw.category),
    city: first(raw.city),
    province: first(raw.province),
    company: first(raw.company),
    education: first(raw.education),
    employment_type: first(raw.employment_type),
    tag: first(raw.tag),
    job_type: first(raw.job_type),
    date: first(raw.date) || first(raw.date_from),
    archive_only: true,
    page,
    page_size: 30,
  };
  const [jobs, filters, stats, branding, pages] = await Promise.all([
    fetchJobs(query),
    fetchFilters(),
    fetchStats(),
    fetchBranding(),
    fetchDirectoryPages(),
  ]);

  return (
    <HomeJobs
      initialJobs={jobs}
      initialQuery={query}
      filters={filters}
      stats={stats}
      branding={branding}
      pages={pages}
      view="archive"
      basePath="/archive"
    />
  );
}
