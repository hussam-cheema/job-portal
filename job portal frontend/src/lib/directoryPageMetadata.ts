import type { Metadata } from "next";
import { fetchDirectoryPage, fetchPublicSeo } from "@/lib/api";
import { decodeHtmlEntities, stripHtml } from "@/lib/format";
import { publicPagePath } from "@/lib/pagePath";
import type { PageType } from "@/lib/types";

export async function directoryPageMetadata(
  pageType: Exclude<PageType, "standard"> | "location",
  slug: string,
): Promise<Metadata> {
  const page = await fetchDirectoryPage(pageType, slug);
  if (!page) {
    return { title: "Page not found", robots: { index: false, follow: false } };
  }
  const seo = await fetchPublicSeo("page", page.id);
  const description = decodeHtmlEntities(
    seo?.meta_description ||
      stripHtml(page.content).replace(/\s+/g, " ").trim().slice(0, 160) ||
      page.title,
  );
  const path = publicPagePath(page);
  const title = decodeHtmlEntities(seo?.meta_title || page.title);
  return {
    title,
    description,
    keywords: seo?.meta_keywords?.split(",").map((value) => value.trim()).filter(Boolean),
    alternates: { canonical: path },
    robots: { index: true, follow: true },
    openGraph: {
      title: decodeHtmlEntities(seo?.og_title || title),
      description: decodeHtmlEntities(seo?.og_description || description),
      type: "website",
      url: path,
      images: seo?.og_image ? [{ url: seo.og_image }] : undefined,
    },
  };
}
