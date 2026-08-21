import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { JobDirectoryList } from "@/components/JobDirectoryList";
import { fetchDirectoryPage } from "@/lib/api";
import { directoryPageMetadata } from "@/lib/directoryPageMetadata";
import { decodeHtmlEntities } from "@/lib/format";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Props = {
  params: Promise<{ newspaper: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { newspaper } = await params;
  return directoryPageMetadata("newspaper", newspaper);
}

export default async function NewspaperPage({ params, searchParams }: Props) {
  const { newspaper: raw } = await params;
  const [cmsPage, search] = await Promise.all([
    fetchDirectoryPage("newspaper", raw),
    searchParams,
  ]);
  if (!cmsPage?.taxonomy_value) notFound();
  const page = Math.max(1, Number(typeof search.page === "string" ? search.page : 1) || 1);
  return (
    <JobDirectoryList
      title={decodeHtmlEntities(cmsPage.title)}
      eyebrow="Newspaper"
      query={{ newspaper: cmsPage.taxonomy_value }}
      page={page}
      basePath={`/newspapers/${cmsPage.slug}`}
      content={cmsPage.content}
    />
  );
}
