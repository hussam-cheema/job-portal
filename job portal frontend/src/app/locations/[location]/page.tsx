import type { Metadata } from "next";
import { JobDirectoryList } from "@/components/JobDirectoryList";
import { fetchFilters } from "@/lib/api";
import { labelFromSlug, toSeoSlug } from "@/lib/slug";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Props = {
  params: Promise<{ location: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { location } = await params;
  const label = labelFromSlug(location);
  return {
    title: `${label} Jobs in Pakistan`,
    description: `Browse current job opportunities in ${label}, Pakistan.`,
    alternates: { canonical: `/locations/${location}` },
    robots: { index: true, follow: true },
  };
}

export default async function LocationPage({ params, searchParams }: Props) {
  const { location: raw } = await params;
  const search = await searchParams;
  const page = Math.max(1, Number(typeof search.page === "string" ? search.page : 1) || 1);
  const filters = await fetchFilters();
  const province = filters.provinces.find((value) => toSeoSlug(value) === raw);
  const city = filters.cities.find((value) => toSeoSlug(value) === raw);
  const location = province || city || labelFromSlug(raw);

  return (
    <JobDirectoryList
      title={`Jobs in ${location}`}
      eyebrow={province ? "Province or territory" : "City"}
      query={province ? { province } : { city: location }}
      page={page}
      basePath={`/locations/${raw}`}
    />
  );
}
