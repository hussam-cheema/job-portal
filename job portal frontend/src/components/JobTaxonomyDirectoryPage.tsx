import { selectSocialImage } from "@/lib/socialMetadata";
import Link from "next/link";
import type { Metadata } from "next";
import { fetchDirectoryPages, fetchPage, fetchPublicSeo } from "@/lib/api";
import { decodeHtmlEntities } from "@/lib/format";
import { wrapRichTextTables } from "@/lib/richText";
import { publicPagePath } from "@/lib/pagePath";
import type { PageType } from "@/lib/types";

type DirectoryKind = "cities" | "provinces" | "categories" | "organizations" | "newspapers";

const configurations: Record<DirectoryKind, {
  slug: string;
  fallbackTitle: string;
  eyebrow: string;
  pageType: Exclude<PageType, "standard">;
  description: string;
}> = {
  cities: {
    slug: "jobs-by-cities",
    fallbackTitle: "Jobs by Cities",
    eyebrow: "Local job directory",
    pageType: "city",
    description: "Browse current jobs in every supported city of Pakistan.",
  },
  provinces: {
    slug: "jobs-by-provinces",
    fallbackTitle: "Jobs by Provinces",
    eyebrow: "Regional job directory",
    pageType: "province",
    description: "Browse jobs across every province and territory of Pakistan.",
  },
  categories: {
    slug: "jobs-by-categories",
    fallbackTitle: "Jobs by Category",
    eyebrow: "Career field directory",
    pageType: "category",
    description: "Browse current Pakistan jobs by profession and category.",
  },
  organizations: {
    slug: "jobs-by-organizations",
    fallbackTitle: "Jobs by Organization",
    eyebrow: "Recruiting organization directory",
    pageType: "organization",
    description: "Browse vacancies by recruiting organization and department.",
  },
  newspapers: {
    slug: "jobs-by-newspapers",
    fallbackTitle: "Jobs by Newspaper",
    eyebrow: "Newspaper job directory",
    pageType: "newspaper",
    description: "Browse current Pakistan job advertisements by newspaper.",
  },
};

export async function jobTaxonomyDirectoryMetadata(kind: DirectoryKind): Promise<Metadata> {
  const config = configurations[kind];
  const page = await fetchPage(config.slug);
  const seo = page ? await fetchPublicSeo("page", page.id) : null;
  const title = decodeHtmlEntities(seo?.meta_title || page?.title || config.fallbackTitle);
  const description = decodeHtmlEntities(seo?.meta_description || config.description);
  return {
    title,
    description,
    keywords: seo?.meta_keywords?.split(",").map((value) => value.trim()).filter(Boolean),
    alternates: { canonical: `/${config.slug}` },
    robots: { index: true, follow: true },
    openGraph: { title, description, type: "website", url: `/${config.slug}`, images: [{ url: selectSocialImage() }] },
  };
}

export async function JobTaxonomyDirectoryPage({ kind }: { kind: DirectoryKind }) {
  const config = configurations[kind];
  const [pages, cmsPage] = await Promise.all([
    fetchDirectoryPages(),
    fetchPage(config.slug),
  ]);
  const values = pages
    .filter((page) => page.page_type === config.pageType && page.taxonomy_value)
    .sort((left, right) => left.title.localeCompare(right.title));
  const title = decodeHtmlEntities(cmsPage?.title || config.fallbackTitle);

  return (
    <main className="site-wrap py-8 sm:py-12">
      <Link href="/" className="inline-flex text-sm text-[var(--muted)] transition hover:text-[var(--blue)]">
        ← Active jobs
      </Link>
      <header className="relative mt-5 overflow-hidden rounded-[2rem] border border-[var(--border)] bg-[linear-gradient(135deg,var(--card),var(--navy-900))] px-5 py-8 shadow-[var(--shadow)] sm:px-9 sm:py-10">
        <div className="pointer-events-none absolute -right-16 -top-24 h-64 w-64 rounded-full bg-[var(--blue)]/15 blur-3xl" />
        <div className="relative max-w-4xl">
          <p className="eyebrow">{config.eyebrow}</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[var(--navy-100)] sm:text-4xl">
            {title}
          </h1>
          {cmsPage?.content ? (
            <div
              className="prose-job mt-4 max-w-3xl text-sm leading-7 text-[var(--muted)] sm:text-base"
              dangerouslySetInnerHTML={{ __html: wrapRichTextTables(cmsPage.content) }}
            />
          ) : (
            <p className="mt-4 text-[var(--muted)]">Choose an entry to view its current job listings.</p>
          )}
          <p className="mt-5 font-mono text-xs text-[var(--navy-300)]">
            {values.length} public {kind === "categories" ? "categories" : kind}
          </p>
        </div>
      </header>

      <section className="mt-7 overflow-hidden rounded-[2rem] border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow)]">
        {values.length ? (
          <ul className="grid gap-px bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-3">
            {values.map((page) => (
              <li key={page.id} className="bg-[var(--card)]">
                <Link
                  href={publicPagePath(page)}
                  className="group flex min-h-16 items-center justify-between gap-4 px-5 py-4 transition hover:bg-[var(--blue-soft)] sm:px-6"
                >
                  <span className="break-words font-medium text-[var(--navy-200)] group-hover:text-[var(--blue)]">
                    {decodeHtmlEntities(page.title)}
                  </span>
                  <span aria-hidden="true" className="shrink-0 text-[var(--muted)] transition group-hover:translate-x-1 group-hover:text-[var(--blue)]">→</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <div className="px-6 py-14 text-center">
            <p className="font-medium text-[var(--navy-200)]">No entries have been published yet.</p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Create and publish a matching directory page from Admin → Pages.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
