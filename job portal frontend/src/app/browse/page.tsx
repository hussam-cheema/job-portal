import type { Metadata } from "next";
import Link from "next/link";
import { fetchBlogFilters, fetchFilters, fetchPages } from "@/lib/api";
import { toSeoSlug } from "@/lib/slug";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Browse Jobs, Organizations and Career Guides",
  description: "Browse Pakistan jobs by category, city, province and organization, plus career guides and application tools.",
  alternates: { canonical: "/browse" },
  robots: { index: true, follow: true },
};

function LinkGroup({ title, values, path }: { title: string; values: string[]; path: string }) {
  if (!values.length) return null;
  return (
    <section className="card-panel p-5 sm:p-7">
      <h2 className="text-xl font-semibold text-[var(--navy-100)]">{title}</h2>
      <div className="mt-4 flex flex-wrap gap-2">
        {values.map((value) => (
          <Link key={value} href={`${path}/${toSeoSlug(value)}`} className="tag tag-blue job-tag-link">
            {value}
          </Link>
        ))}
      </div>
    </section>
  );
}

export default async function BrowsePage() {
  const [filters, blogFilters, pages] = await Promise.all([
    fetchFilters(), fetchBlogFilters(), fetchPages(),
  ]);
  const core = new Set(["about", "contact", "privacy", "disclaimer"]);
  const customPages = pages.filter((page) => !core.has(page.slug));
  return (
    <div className="site-wrap py-8 sm:py-12">
      <header className="mb-7 max-w-3xl">
        <p className="eyebrow">Site directory</p>
        <h1 className="mt-2 text-3xl font-semibold text-[var(--navy-100)] sm:text-4xl">Browse every opportunity and resource</h1>
        <p className="mt-3 text-[var(--muted)]">A crawlable directory of job categories, locations, employers and career resources.</p>
      </header>
      <div className="grid gap-5 lg:grid-cols-2">
        <LinkGroup title="Job categories" values={filters.categories} path="/categories" />
        <LinkGroup title="Organizations" values={filters.companies} path="/companies" />
        <LinkGroup title="Provinces" values={filters.provinces} path="/locations" />
        <LinkGroup title="Cities" values={filters.cities} path="/locations" />
        <LinkGroup title="Qualifications" values={filters.qualifications || []} path="/qualifications" />
        <LinkGroup title="Career guide categories" values={blogFilters.categories} path="/blog/categories" />
        <LinkGroup title="Career guide topics" values={blogFilters.tags} path="/blog/tags" />
        <section className="card-panel p-5 sm:p-7">
          <h2 className="text-xl font-semibold text-[var(--navy-100)]">Career tools</h2>
          <nav className="mt-4 flex flex-wrap gap-3">
            <Link href="/resume-builder" className="btn btn-ghost">ATS Resume Builder</Link>
            <Link href="/cover-letter" className="btn btn-ghost">Cover Letter Builder</Link>
            <Link href="/blog" className="btn btn-ghost">Career guides</Link>
          </nav>
        </section>
        {customPages.length > 0 && (
          <section className="card-panel p-5 sm:p-7">
            <h2 className="text-xl font-semibold text-[var(--navy-100)]">More resources</h2>
            <nav className="mt-4 flex flex-wrap gap-3">
              {customPages.map((page) => <Link key={page.id} href={`/p/${page.slug}`} className="btn btn-ghost">{page.title}</Link>)}
            </nav>
          </section>
        )}
      </div>
    </div>
  );
}
