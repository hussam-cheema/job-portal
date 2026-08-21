import { notFound } from "next/navigation";
import { JobDirectoryList } from "@/components/JobDirectoryList";
import { fetchDirectoryPage } from "@/lib/api";
import { directoryPageMetadata } from "@/lib/directoryPageMetadata";
import { decodeHtmlEntities } from "@/lib/format";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Props = {
  params: Promise<{ company: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({ params }: Props) {
  const { company } = await params;
  return directoryPageMetadata("organization", company);
}

export default async function CompanyPage({ params, searchParams }: Props) {
  const { company: raw } = await params;
  const [cmsPage, search] = await Promise.all([
    fetchDirectoryPage("organization", raw),
    searchParams,
  ]);
  if (!cmsPage?.taxonomy_value) notFound();
  const page = Math.max(1, Number(typeof search.page === "string" ? search.page : 1) || 1);
  return (
    <JobDirectoryList
      title={decodeHtmlEntities(cmsPage.title)}
      eyebrow="Organization"
      query={{ company: cmsPage.taxonomy_value }}
      page={page}
      basePath={`/companies/${cmsPage.slug}`}
      content={cmsPage.content}
    />
  );
}
