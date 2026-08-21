import Link from "next/link";
import type { DirectoryPageLink, PageType } from "@/lib/types";
import { publicPagePath } from "@/lib/pagePath";

type DiscoveryGroup = {
  title: string;
  eyebrow: string;
  pages: DirectoryPageLink[];
  moreHref: string;
  moreLabel: string;
};

const featuredCities = [
  "Lahore",
  "Karachi",
  "Islamabad",
  "Rawalpindi",
  "Peshawar",
  "Quetta",
];

function featured(pages: DirectoryPageLink[], pageType: PageType, preferred: string[] = []) {
  const byKey = new Map(
    pages
      .filter((page) => page.page_type === pageType && page.taxonomy_value)
      .map((page) => [page.taxonomy_value!.toLocaleLowerCase(), page]),
  );
  const result: DirectoryPageLink[] = [];
  for (const value of preferred) {
    const match = byKey.get(value.toLocaleLowerCase());
    if (match && !result.some((page) => page.id === match.id)) result.push(match);
  }
  for (const page of [...byKey.values()].sort((left, right) => left.title.localeCompare(right.title))) {
    if (!result.some((entry) => entry.id === page.id)) result.push(page);
  }
  return result.slice(0, 6);
}

export function JobDiscoverySection({ pages }: { pages: DirectoryPageLink[] }) {
  const groups: DiscoveryGroup[] = [
    {
      title: "Jobs by Cities",
      eyebrow: "Local opportunities",
      pages: featured(pages, "city", featuredCities),
      moreHref: "/jobs-by-cities",
      moreLabel: "More cities…",
    },
    {
      title: "Jobs by Provinces",
      eyebrow: "Regional coverage",
      pages: featured(pages, "province"),
      moreHref: "/jobs-by-provinces",
      moreLabel: "More provinces…",
    },
    {
      title: "Jobs by Category",
      eyebrow: "Career fields",
      pages: featured(pages, "category"),
      moreHref: "/jobs-by-categories",
      moreLabel: "More categories…",
    },
    {
      title: "Jobs by Organization",
      eyebrow: "Recruiting bodies",
      pages: featured(pages, "organization"),
      moreHref: "/jobs-by-organizations",
      moreLabel: "More organizations…",
    },
    {
      title: "Jobs by Newspaper",
      eyebrow: "Published adverts",
      pages: featured(pages, "newspaper"),
      moreHref: "/jobs-by-newspapers",
      moreLabel: "More newspapers…",
    },
  ];

  return (
    <section className="mt-8 overflow-hidden rounded-[2rem] border border-[var(--border)] bg-[linear-gradient(145deg,var(--card),var(--navy-900))] shadow-[var(--shadow)]">
      <header className="relative overflow-hidden border-b border-[var(--border)] px-5 py-7 sm:px-8">
        <div className="pointer-events-none absolute -right-12 -top-20 h-48 w-48 rounded-full bg-[var(--blue)]/15 blur-3xl" />
        <div className="relative">
          <p className="eyebrow">Explore opportunities</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--navy-100)] sm:text-3xl">
            Find jobs your way
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)] sm:text-base">
            Browse current openings by location, career field, recruiting organization, or newspaper.
          </p>
        </div>
      </header>

      <div className="grid gap-px bg-[var(--border)] md:grid-cols-2 xl:grid-cols-5">
        {groups.map((group) => (
          <article key={group.title} className="flex min-h-full flex-col bg-[var(--card)] p-5 sm:p-6">
            <p className="text-[10px] font-semibold uppercase tracking-[0.17em] text-[var(--blue)]">
              {group.eyebrow}
            </p>
            <h3 className="mt-2 border-b border-[var(--border)] pb-3 text-lg font-semibold text-[var(--navy-100)]">
              {group.title}
            </h3>
            <ul className="mt-3 flex-1 space-y-1">
              {group.pages.map((page) => (
                <li key={page.id}>
                  <Link
                    href={publicPagePath(page)}
                    className="group flex min-h-10 items-center gap-2 rounded-xl px-2.5 py-2 text-sm font-medium text-[var(--navy-300)] transition hover:bg-[var(--blue-soft)] hover:text-[var(--blue)]"
                  >
                    <span aria-hidden="true" className="text-[var(--muted)] transition group-hover:translate-x-0.5 group-hover:text-[var(--blue)]">›</span>
                    <span className="break-words">{page.title}</span>
                  </Link>
                </li>
              ))}
            </ul>
            <Link
              href={group.moreHref}
              className="mt-4 inline-flex min-h-11 items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--navy-900)]/45 px-4 py-2.5 text-sm font-semibold text-[var(--navy-100)] transition hover:border-[var(--blue)] hover:bg-[var(--blue-soft)] hover:text-[var(--blue)]"
            >
              {group.moreLabel}
              <span aria-hidden="true">→</span>
            </Link>
          </article>
        ))}
      </div>
    </section>
  );
}
