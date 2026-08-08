import type { Metadata } from "next";
import { JobDirectoryList } from "@/components/JobDirectoryList";
import { fetchFilters } from "@/lib/api";
import { labelFromSlug, toSeoSlug } from "@/lib/slug";

type Props = { params: Promise<{ location: string }> };

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

export default async function LocationPage({ params }: Props) {
  const { location: raw } = await params;
  const filters = await fetchFilters();
  const province = filters.provinces.find((value) => toSeoSlug(value) === raw);
  const city = filters.cities.find((value) => toSeoSlug(value) === raw);
  const location = province || city || labelFromSlug(raw);

  return (
    <JobDirectoryList
      title={`Jobs in ${location}`}
      eyebrow={province ? "Province or territory" : "City"}
      query={province ? { province } : { city: location }}
    />
  );
}
