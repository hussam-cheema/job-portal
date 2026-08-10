import type { Metadata } from "next";
import { Suspense } from "react";
import { HomeJobs } from "@/components/HomeJobs";
import { fetchBranding, fetchFilters, fetchJobs, fetchStats } from "@/lib/api";
import type { JobQuery } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

function homepageKeywords(value: string) {
  return Array.from(
    new Set(
      value
        .split(",")
        .map((keyword) => keyword.trim())
        .filter(Boolean)
    )
  );
}

export async function generateMetadata(): Promise<Metadata> {
  const branding = await fetchBranding();
  const title = branding.homepage_meta_title.trim() || branding.site_title;
  const description =
    branding.homepage_meta_description.trim() || branding.site_description;

  return {
    title: { absolute: title },
    description,
    keywords: homepageKeywords(
      `${branding.homepage_focus_keyword},${branding.homepage_meta_keywords}`
    ),
    alternates: { canonical: "/" },
    openGraph: {
      title,
      description,
      type: "website",
      url: "/",
      siteName: branding.site_name,
    },
    twitter: {
      card: "summary",
      title,
      description,
    },
  };
}

type HomePageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function HomePage({ searchParams }: HomePageProps) {
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
    page,
    page_size: 30,
  };
  const [jobs, filters, stats, branding] = await Promise.all([
    fetchJobs(query),
    fetchFilters(),
    fetchStats(),
    fetchBranding(),
  ]);

  return (
    <Suspense
      fallback={
        <div className="site-wrap py-10">
          <div className="h-96 animate-pulse rounded-xl bg-[var(--card)]" />
        </div>
      }
    >
      <HomeJobs
        initialJobs={jobs}
        filters={filters}
        stats={stats}
        branding={branding}
      />
    </Suspense>
  );
}
