import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { JobDirectoryList } from "@/components/JobDirectoryList";
import { fetchDirectoryPage } from "@/lib/api";
import { directoryPageMetadata } from "@/lib/directoryPageMetadata";
import { decodeHtmlEntities } from "@/lib/format";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Props = {
  params: Promise<{ location: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { location } = await params;
  return directoryPageMetadata("location", location);
}

export default async function LocationPage({ params, searchParams }: Props) {
  const { location: raw } = await params;
  const [cmsPage, search] = await Promise.all([
    fetchDirectoryPage("location", raw),
    searchParams,
  ]);
  if (!cmsPage?.taxonomy_value) notFound();
  const page = Math.max(1, Number(typeof search.page === "string" ? search.page : 1) || 1);
  const location = cmsPage.taxonomy_value;
  const isProvince = cmsPage.page_type === "province";

  return (
    <JobDirectoryList
      title={decodeHtmlEntities(cmsPage.title)}
      eyebrow={isProvince ? "Province or territory" : "City"}
      query={isProvince ? { province: location } : { city: location }}
      page={page}
      basePath={`/locations/${cmsPage.slug}`}
      content={cmsPage.content}
    />
  );
}
