import { JobDirectoryList } from "@/components/JobDirectoryList";
import { fetchFilters } from "@/lib/api";
import { labelFromSlug, toSeoSlug } from "@/lib/slug";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Props = { params: Promise<{ company: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };
export async function generateMetadata({ params }: Props) {
  const { company } = await params; const label = labelFromSlug(company);
  return { title: `${label} Jobs in Pakistan`, description: `Browse current ${label} jobs and career opportunities in Pakistan.`, alternates: { canonical: `/companies/${company}` }, robots: { index: true, follow: true } };
}
export default async function CompanyPage({ params, searchParams }: Props) {
  const { company: raw } = await params; const filters = await fetchFilters();
  const search = await searchParams; const page = Math.max(1, Number(typeof search.page === "string" ? search.page : 1) || 1);
  const company = filters.companies.find((value) => toSeoSlug(value) === raw) || labelFromSlug(raw);
  return <JobDirectoryList title={`${company} jobs`} eyebrow="Organization" query={{ company }} page={page} basePath={`/companies/${raw}`} />;
}
