import type { Metadata } from "next";
import Link from "next/link";
import { Pagination } from "@/components/Pagination";
import { fetchBlogFilters, fetchBlogPosts } from "@/lib/api";
import { decodeHtmlEntities, formatDate, stripHtml } from "@/lib/format";
import { toSeoSlug } from "@/lib/slug";

type Props = {
  searchParams: Promise<{ q?: string; category?: string; tag?: string; page?: string }>;
};

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Career Guidance and Job Updates",
  description:
    "Read practical guidance for job applications, interviews, careers and employment opportunities across Pakistan.",
  alternates: { canonical: "/blog" },
  robots: { index: true, follow: true },
};

export default async function BlogPage({ searchParams }: Props) {
  const query = await searchParams;
  const page = Math.max(1, Number(query.page) || 1);
  const [result, filters] = await Promise.all([
    fetchBlogPosts({ q: query.q, category: query.category, tag: query.tag, page }),
    fetchBlogFilters(),
  ]);

  return (
    <div className="site-wrap py-8 sm:py-12">
      <header className="mb-7">
        <p className="eyebrow">Pakistan Jobs Market Blog</p>
        <h1 className="mt-2 text-3xl sm:text-4xl font-semibold tracking-tight text-[var(--navy-100)]">
          Career guidance and job updates
        </h1>
        <p className="mt-3 max-w-2xl text-[var(--muted)]">
          Practical advice for applications, interviews, careers, and opportunities in Pakistan.
        </p>
      </header>

      <form action="/blog" className="card-panel mb-6 grid gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_12rem_12rem_auto]">
        <input name="q" defaultValue={query.q} className="input" placeholder="Search blog posts…" aria-label="Search blog posts" />
        <select name="category" defaultValue={query.category || ""} className="input" aria-label="Filter by category">
          <option value="">All categories</option>
          {filters.categories.map((value) => <option key={value}>{value}</option>)}
        </select>
        <select name="tag" defaultValue={query.tag || ""} className="input" aria-label="Filter by tag">
          <option value="">All tags</option>
          {filters.tags.map((value) => <option key={value}>{value}</option>)}
        </select>
        <button className="btn btn-primary" type="submit">Filter</button>
      </form>

      {result.items.length ? (
        <div className="space-y-4">
          <div className="grid gap-4">
            {result.items.map((post) => (
              <article key={post.id} data-testid="blog-card" className="blog-list-card card-panel group p-5 sm:p-7">
                <div className="grid min-w-0 gap-5 sm:grid-cols-[9rem_minmax(0,1fr)_auto] sm:items-center">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--muted)] sm:block">
                    <time className="font-medium text-[var(--navy-300)]">{formatDate(post.published_at || post.created_at)}</time>
                    {post.category && <div className="mt-0 sm:mt-3"><Link href={`/blog/categories/${toSeoSlug(post.category)}`} className="tag tag-blue job-tag-link">{decodeHtmlEntities(post.category)}</Link></div>}
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-xl font-semibold leading-snug text-[var(--navy-100)] sm:text-2xl">
                      <Link href={`/blog/${post.slug}`} className="break-words transition-colors group-hover:text-[var(--accent)]">{decodeHtmlEntities(post.title)}</Link>
                    </h2>
                    <p className="mt-2 line-clamp-3 text-sm leading-6 text-[var(--navy-300)]">
                      {decodeHtmlEntities(post.excerpt || stripHtml(post.content).slice(0, 260))}
                    </p>
                    {post.tags.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {post.tags.slice(0, 5).map((tag) => <Link key={tag} href={`/blog/tags/${toSeoSlug(tag)}`} className="tag tag-blue job-tag-link">{decodeHtmlEntities(tag)}</Link>)}
                      </div>
                    )}
                  </div>
                  <Link href={`/blog/${post.slug}`} className="btn btn-ghost w-fit whitespace-nowrap text-sm font-semibold group-hover:border-[var(--accent)] group-hover:text-[var(--accent)]">
                    Read article →
                  </Link>
                </div>
              </article>
            ))}
          </div>
          <div className="card-panel">
            <Pagination page={result.page} pages={result.pages} total={result.total} query={query} basePath="/blog" itemLabel="post" />
          </div>
        </div>
      ) : (
        <div className="card-panel p-8 text-center text-[var(--muted)]">
          No blog posts matched these filters.
        </div>
      )}
    </div>
  );
}
