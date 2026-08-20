import type { Metadata } from "next";
import { JobDirectoryList } from "@/components/JobDirectoryList";
import { fetchFilters } from "@/lib/api";
import { labelFromSlug, toSeoSlug } from "@/lib/slug";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Props = {
  params: Promise<{ newspaper: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { newspaper } = await params;
  const label = labelFromSlug(newspaper);
  return {
    title: `${label} Jobs in Pakistan`,
    description: `Browse current Pakistan job advertisements published in ${label}.`,
    alternates: { canonical: `/newspapers/${newspaper}` },
    robots: { index: true, follow: true },
  };
}

export default async function NewspaperPage({ params, searchParams }: Props) {
  const { newspaper: raw } = await params;
  const [filters, search] = await Promise.all([fetchFilters(), searchParams]);
  const newspaper =
    filters.newspapers.find((value) => toSeoSlug(value) === raw) || labelFromSlug(raw);
  const page = Math.max(1, Number(typeof search.page === "string" ? search.page : 1) || 1);
  return (
    <JobDirectoryList
      title={`Jobs in ${newspaper}`}
      eyebrow="Newspaper"
      query={{ newspaper }}
      page={page}
      basePath={`/newspapers/${raw}`}
    />
  );
}
