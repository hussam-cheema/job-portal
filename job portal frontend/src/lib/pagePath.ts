import type { DirectoryPageLink, PageItem, PageType } from "@/lib/types";

export const directoryPagePaths: Record<Exclude<PageType, "standard">, string> = {
  city: "/locations",
  province: "/locations",
  category: "/categories",
  organization: "/companies",
  newspaper: "/newspapers",
};

const directPageSlugs = new Set([
  "about",
  "contact",
  "privacy",
  "disclaimer",
  "jobs-by-cities",
  "jobs-by-provinces",
  "jobs-by-categories",
  "jobs-by-organizations",
  "jobs-by-newspapers",
]);

export function publicPagePath(page: Pick<PageItem, "page_type" | "slug">) {
  if (page.page_type !== "standard") {
    return `${directoryPagePaths[page.page_type]}/${page.slug}`;
  }
  return directPageSlugs.has(page.slug) ? `/${page.slug}` : `/p/${page.slug}`;
}

export function pagePathPrefix(page: Pick<PageItem, "page_type" | "slug">) {
  if (page.page_type !== "standard") return `${directoryPagePaths[page.page_type]}/`;
  return directPageSlugs.has(page.slug) ? "/" : "/p/";
}

export function findDirectoryPage(
  pages: DirectoryPageLink[],
  pageType: DirectoryPageLink["page_type"],
  taxonomyValue?: string | null,
) {
  const key = taxonomyValue?.trim().toLocaleLowerCase();
  if (!key) return undefined;
  return pages.find(
    (page) =>
      page.page_type === pageType &&
      page.taxonomy_value.trim().toLocaleLowerCase() === key,
  );
}
