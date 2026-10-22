import { JobDirectoryList } from "@/components/JobDirectoryList";
import { fetchFilters, fetchJobs } from "@/lib/api";
import { labelFromSlug, toSeoSlug } from "@/lib/slug";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Props = { params: Promise<{ qualification: string }> };
export async function generateMetadata({ params }: Props) {
  const { qualification } = await params;
  const filters = await fetchFilters();
  const label =
    filters.qualifications?.find((value) => toSeoSlug(value) === qualification) ||
    labelFromSlug(qualification);
  const indexableJobs = await fetchJobs({
    education: label,
    indexable_only: true,
    page_size: 1,
  });
  return {
    title: `${label} Qualification Jobs in Pakistan`,
    description: `Find Pakistan jobs requiring ${label}.`,
    alternates: { canonical: `/qualifications/${qualification}` },
    robots: { index: indexableJobs.total > 0, follow: true },
  };
}
export default async function QualificationPage({ params }: Props) {
  const { qualification } = await params;
  const filters = await fetchFilters();
  const label = filters.qualifications?.find((value) => toSeoSlug(value) === qualification) || labelFromSlug(qualification);
  return <JobDirectoryList title={`Jobs requiring ${label}`} eyebrow="Qualification" query={{ education: label }} />;
}
