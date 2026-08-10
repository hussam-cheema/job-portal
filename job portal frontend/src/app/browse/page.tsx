import type { Metadata } from "next";
import Link from "next/link";
import { fetchSiteDirectory } from "@/lib/api";
import type { DirectoryValue } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export const metadata: Metadata = {
  title: "Browse All Jobs, Organizations and Career Guides",
  description:
    "Browse every Pakistan job, organization, category, city, province, career guide, public page and application tool in one crawlable directory.",
  alternates: { canonical: "/browse" },
  robots: { index: true, follow: true },
};

const corePages = [
  { href: "/", label: "Latest jobs" },
  { href: "/browse", label: "Browse All" },
  { href: "/blog", label: "Career guides" },
  { href: "/about", label: "About us" },
  { href: "/contact", label: "Contact" },
  { href: "/privacy", label: "Privacy policy" },
  { href: "/disclaimer", label: "Disclaimer" },
];

const corePageSlugs = new Set(["about", "contact", "privacy", "disclaimer"]);

const careerTools = [
  {
    href: "/resume-builder",
    label: "ATS Resume Builder",
    description: "Build and score an ATS-friendly resume.",
  },
  {
    href: "/cover-letter",
    label: "Cover Letter Builder",
    description: "Create a polished, editable cover letter.",
  },
];

function countLabel(count: number, singular: string, plural = `${singular}s`) {
  return `${count.toLocaleString()} ${count === 1 ? singular : plural}`;
}

function DirectoryLinks({
  id,
  title,
  eyebrow,
  values,
  path,
}: {
  id: string;
  title: string;
  eyebrow: string;
  values: DirectoryValue[];
  path: string;
}) {
  if (!values.length) return null;
  return (
    <section id={id} className="card-panel scroll-mt-24 overflow-hidden p-5 sm:p-7">
      <div className="flex items-end justify-between gap-4 border-b border-[var(--border)] pb-4">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2 className="mt-1 text-2xl font-semibold text-[var(--navy-100)]">{title}</h2>
        </div>
        <span className="rounded-full bg-[var(--navy-800)] px-3 py-1 font-mono text-xs text-[var(--navy-300)]">
          {values.length}
        </span>
      </div>
      <ul className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {values.map((value) => (
          <li key={`${path}-${value.slug}`}>
            <Link
              href={`${path}/${value.slug}`}
              className="group flex min-h-12 items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--navy-900)]/35 px-4 py-3 transition hover:-translate-y-0.5 hover:border-[var(--blue)] hover:bg-[var(--blue-soft)]"
            >
              <span className="min-w-0 break-words font-medium text-[var(--navy-200)] group-hover:text-[var(--navy-100)]">
                {value.name}
              </span>
              {value.count > 0 && (
                <span className="shrink-0 font-mono text-[11px] text-[var(--muted)]">
                  {value.count}
                </span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default async function BrowsePage() {
  const directory = await fetchSiteDirectory();
  const customPages = directory.pages.filter(
    (page) => !corePageSlugs.has(page.slug)
  );
  const publicPages = [
    ...corePages,
    ...customPages.map((page) => ({ href: page.path, label: page.title })),
  ];
  const taxonomyCount = Object.values(directory.taxonomies).reduce(
    (total, values) => total + values.length,
    0
  );

  return (
    <main className="site-wrap py-8 sm:py-12">
      <header className="relative overflow-hidden rounded-[2rem] border border-[var(--border)] bg-[linear-gradient(135deg,var(--card),var(--navy-900))] px-5 py-9 shadow-[var(--shadow)] sm:px-10 sm:py-12">
        <div className="pointer-events-none absolute -right-16 -top-24 h-64 w-64 rounded-full bg-[var(--blue)]/15 blur-3xl" />
        <div className="relative max-w-4xl">
          <p className="eyebrow">Complete public site directory</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight text-[var(--navy-100)] sm:text-5xl">
            Browse every opportunity and resource
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-[var(--muted)] sm:text-lg">
            Every public job, guide, organization, location, topic and career tool is linked here in server-rendered HTML for people and search engines.
          </p>
          <dl className="mt-8 grid max-w-3xl grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              [directory.jobs.length, "job"],
              [directory.blogs.length, "guide"],
              [taxonomyCount, "directory link"],
              [publicPages.length, "page"],
            ].map(([count, label]) => (
              <div key={String(label)} className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/70 p-4 backdrop-blur">
                <dt className="text-xs uppercase tracking-[0.16em] text-[var(--muted)]">{String(label)}</dt>
                <dd className="mt-1 text-2xl font-semibold text-[var(--navy-100)]">{Number(count).toLocaleString()}</dd>
              </div>
            ))}
          </dl>
        </div>
      </header>

      <nav aria-label="Browse All sections" className="my-7 flex flex-wrap gap-2">
        {[
          ["jobs", "All jobs"],
          ["blogs", "All guides"],
          ["categories", "Categories"],
          ["organizations", "Organizations"],
          ["cities", "Cities"],
          ["provinces", "Provinces"],
          ["job-tags", "Job tags"],
          ["pages", "Pages & tools"],
        ].map(([id, label]) => (
          <a key={id} href={`#${id}`} className="tag tag-blue job-tag-link">
            {label}
          </a>
        ))}
      </nav>

      <div className="space-y-6">
        <section id="jobs" className="card-panel scroll-mt-24 overflow-hidden">
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--border)] px-5 py-6 sm:px-7">
            <div>
              <p className="eyebrow">Opportunities</p>
              <h2 className="mt-1 text-2xl font-semibold text-[var(--navy-100)]">All job posts</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">Permanent canonical links remain available after application deadlines.</p>
            </div>
            <span className="font-mono text-xs text-[var(--navy-300)]">
              {countLabel(directory.jobs.length, "job")}
            </span>
          </div>
          {directory.jobs.length ? (
            <ul className="divide-y divide-[var(--border)]">
              {directory.jobs.map((job) => (
                <li key={job.id}>
                  <Link href={`/jobs/${job.slug}`} className="group grid gap-2 px-5 py-4 transition hover:bg-[var(--blue-soft)] sm:grid-cols-[1fr_auto] sm:items-center sm:px-7">
                    <span className="min-w-0">
                      <span className="block break-words font-semibold text-[var(--navy-100)] group-hover:text-[var(--blue)]">{job.title}</span>
                      <span className="mt-1 block text-sm text-[var(--muted)]">
                        {[job.organization, ...job.cities, ...job.provinces].filter(Boolean).join(" · ") || "Pakistan"}
                      </span>
                    </span>
                    <span className={`w-fit rounded-full px-3 py-1 text-xs font-semibold ${job.applications_closed ? "bg-[var(--navy-800)] text-[var(--muted)]" : "bg-emerald-500/10 text-emerald-400"}`}>
                      {job.applications_closed ? "Applications closed" : "Open"}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-7 py-10 text-[var(--muted)]">No public jobs are available yet.</p>
          )}
        </section>

        <section id="blogs" className="card-panel scroll-mt-24 overflow-hidden">
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--border)] px-5 py-6 sm:px-7">
            <div>
              <p className="eyebrow">Knowledge library</p>
              <h2 className="mt-1 text-2xl font-semibold text-[var(--navy-100)]">All career guides</h2>
            </div>
            <span className="font-mono text-xs text-[var(--navy-300)]">
              {countLabel(directory.blogs.length, "guide")}
            </span>
          </div>
          {directory.blogs.length ? (
            <ul className="grid gap-px bg-[var(--border)] sm:grid-cols-2">
              {directory.blogs.map((post) => (
                <li key={post.id} className="bg-[var(--card)]">
                  <Link href={`/blog/${post.slug}`} className="group block h-full px-5 py-5 transition hover:bg-[var(--blue-soft)] sm:px-7">
                    <span className="block text-xs font-semibold uppercase tracking-[0.14em] text-[var(--blue)]">{post.category || "Career guide"}</span>
                    <span className="mt-2 block break-words text-lg font-semibold leading-6 text-[var(--navy-100)] group-hover:text-[var(--blue)]">{post.title}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-7 py-10 text-[var(--muted)]">No published guides are available yet.</p>
          )}
        </section>

        <div className="grid gap-6 lg:grid-cols-2">
          <DirectoryLinks id="categories" title="Job categories" eyebrow="Browse by field" values={directory.taxonomies.job_categories} path="/categories" />
          <DirectoryLinks id="organizations" title="Organizations" eyebrow="Browse by employer" values={directory.taxonomies.organizations} path="/companies" />
          <DirectoryLinks id="cities" title="Cities" eyebrow="Browse locally" values={directory.taxonomies.cities} path="/locations" />
          <DirectoryLinks id="provinces" title="Provinces" eyebrow="Browse regionally" values={directory.taxonomies.provinces} path="/locations" />
          <DirectoryLinks id="job-tags" title="Job tags" eyebrow="Browse by topic" values={directory.taxonomies.job_tags} path="/tags" />
          <DirectoryLinks id="qualifications" title="Qualifications" eyebrow="Browse by education" values={directory.taxonomies.qualifications} path="/qualifications" />
          <DirectoryLinks id="blog-categories" title="Guide categories" eyebrow="Career library" values={directory.taxonomies.blog_categories} path="/blog/categories" />
          <DirectoryLinks id="blog-tags" title="Guide topics" eyebrow="Career library" values={directory.taxonomies.blog_tags} path="/blog/tags" />
        </div>

        <section id="pages" className="card-panel scroll-mt-24 p-5 sm:p-7">
          <div className="border-b border-[var(--border)] pb-4">
            <p className="eyebrow">Website resources</p>
            <h2 className="mt-1 text-2xl font-semibold text-[var(--navy-100)]">Pages and career tools</h2>
          </div>
          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <div>
              <h3 className="font-semibold text-[var(--navy-200)]">Public pages</h3>
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {publicPages.map((page) => (
                  <li key={`${page.href}-${page.label}`}>
                    <Link href={page.href} className="block rounded-xl border border-[var(--border)] px-4 py-3 font-medium text-[var(--navy-200)] transition hover:border-[var(--blue)] hover:bg-[var(--blue-soft)] hover:text-[var(--blue)]">{page.label}</Link>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="font-semibold text-[var(--navy-200)]">Career tools</h3>
              <ul className="mt-3 space-y-2">
                {careerTools.map((tool) => (
                  <li key={tool.href}>
                    <Link href={tool.href} className="group block rounded-xl border border-[var(--border)] px-4 py-3 transition hover:border-[var(--blue)] hover:bg-[var(--blue-soft)]">
                      <span className="font-semibold text-[var(--navy-100)] group-hover:text-[var(--blue)]">{tool.label}</span>
                      <span className="mt-1 block text-sm text-[var(--muted)]">{tool.description}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
