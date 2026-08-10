import { JobDirectoryList } from "@/components/JobDirectoryList";
import { fetchFilters } from "@/lib/api";
import { labelFromSlug, toSeoSlug } from "@/lib/slug";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Props = { params: Promise<{ company: string }> };
export async function generateMetadata({ params }: Props) {
  const { company } = await params; const label = labelFromSlug(company);
  return { title: `${label} Jobs in Pakistan`, description: `Browse current ${label} jobs and career opportunities in Pakistan.`, alternates: { canonical: `/companies/${company}` }, robots: { index: true, follow: true } };
}
export default async function CompanyPage({ params }: Props) {
  const { company: raw } = await params; const filters = await fetchFilters();
  const company = filters.companies.find((value) => toSeoSlug(value) === raw) || labelFromSlug(raw);
  return <JobDirectoryList title={`${company} jobs`} eyebrow="Organization" query={{ company }} />;
}
