import type { Metadata } from "next";
import { Suspense } from "react";
import { HomeJobs } from "@/components/HomeJobs";
import { fetchBranding, fetchFilters, fetchJobs, fetchStats } from "@/lib/api";

export const revalidate = 15;

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

export default async function HomePage() {
  const [jobs, filters, stats, branding] = await Promise.all([
    fetchJobs({ page: 1, page_size: 30 }),
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
