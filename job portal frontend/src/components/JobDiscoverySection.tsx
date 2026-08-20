import Link from "next/link";
import type { FiltersResponse } from "@/lib/types";
import { toSeoSlug } from "@/lib/slug";

type DiscoveryGroup = {
  title: string;
  eyebrow: string;
  values: string[];
  href: (value: string) => string;
  label: (value: string) => string;
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

function featured(values: string[], preferred: string[] = []) {
  const byKey = new Map(
    values.filter(Boolean).map((value) => [value.toLocaleLowerCase(), value]),
  );
  const result: string[] = [];
  for (const value of preferred) {
    const match = byKey.get(value.toLocaleLowerCase());
    if (match && !result.includes(match)) result.push(match);
  }
  for (const value of [...values].sort((left, right) => left.localeCompare(right))) {
    if (!result.includes(value)) result.push(value);
  }
  return result.slice(0, 6);
}

export function JobDiscoverySection({ filters }: { filters: FiltersResponse }) {
  const groups: DiscoveryGroup[] = [
    {
      title: "Jobs by Cities",
      eyebrow: "Local opportunities",
      values: featured(filters.cities, featuredCities),
      href: (value) => `/locations/${toSeoSlug(value)}`,
      label: (value) => `Jobs in ${value}`,
      moreHref: "/jobs-by-cities",
      moreLabel: "More cities…",
    },
    {
      title: "Jobs by Provinces",
      eyebrow: "Regional coverage",
      values: featured(filters.provinces),
      href: (value) => `/locations/${toSeoSlug(value)}`,
      label: (value) => `Jobs in ${value}`,
      moreHref: "/jobs-by-provinces",
      moreLabel: "More provinces…",
    },
    {
      title: "Jobs by Category",
      eyebrow: "Career fields",
      values: featured(filters.categories),
      href: (value) => `/categories/${toSeoSlug(value)}`,
      label: (value) => `${value} Jobs`,
      moreHref: "/jobs-by-categories",
      moreLabel: "More categories…",
    },
    {
      title: "Jobs by Organization",
      eyebrow: "Recruiting bodies",
      values: featured(filters.companies),
      href: (value) => `/companies/${toSeoSlug(value)}`,
      label: (value) => `${value} Jobs`,
      moreHref: "/jobs-by-organizations",
      moreLabel: "More organizations…",
    },
    {
      title: "Jobs by Newspaper",
      eyebrow: "Published adverts",
      values: featured(filters.newspapers || []),
      href: (value) => `/newspapers/${toSeoSlug(value)}`,
      label: (value) => `Jobs in ${value}`,
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
              {group.values.map((value) => (
                <li key={`${group.title}-${value}`}>
                  <Link
                    href={group.href(value)}
                    className="group flex min-h-10 items-center gap-2 rounded-xl px-2.5 py-2 text-sm font-medium text-[var(--navy-300)] transition hover:bg-[var(--blue-soft)] hover:text-[var(--blue)]"
                  >
                    <span aria-hidden="true" className="text-[var(--muted)] transition group-hover:translate-x-0.5 group-hover:text-[var(--blue)]">›</span>
                    <span className="break-words">{group.label(value)}</span>
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
