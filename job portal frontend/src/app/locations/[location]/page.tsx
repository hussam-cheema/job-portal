import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import { JobDirectoryList } from "@/components/JobDirectoryList";
import { fetchDirectoryPage } from "@/lib/api";
import {
  directoryPageMetadata,
  normalizeDirectoryTitle,
} from "@/lib/directoryPageMetadata";

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
  const requestedPage =
    typeof search.page === "string" ? search.page.trim() : undefined;
  const page = Math.max(1, Number(requestedPage || 1) || 1);
  const basePath = `/locations/${cmsPage.slug}`;
  const onlyCanonicalPageParam =
    Object.keys(search).every((key) => key === "page") &&
    (requestedPage === undefined ||
      (typeof search.page === "string" && /^\d+$/.test(requestedPage)));
  if (
    Object.keys(search).length > 0 &&
    (!onlyCanonicalPageParam || page === 1 || requestedPage !== String(page))
  ) {
    permanentRedirect(page > 1 ? `${basePath}?page=${page}` : basePath);
  }
  const location = cmsPage.taxonomy_value;
  const isProvince = cmsPage.page_type === "province";

  return (
    <JobDirectoryList
      title={normalizeDirectoryTitle(cmsPage.title)}
      eyebrow={isProvince ? "Province or territory" : "City"}
      query={isProvince ? { province: location } : { city: location }}
      page={page}
      basePath={basePath}
      content={cmsPage.content}
    />
  );
}
