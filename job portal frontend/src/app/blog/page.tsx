import Link from "next/link";
import { Pagination } from "@/components/Pagination";
import { fetchBlogFilters, fetchBlogPosts } from "@/lib/api";
import { formatDate, stripHtml } from "@/lib/format";

type Props = {
  searchParams: Promise<{ q?: string; category?: string; tag?: string; page?: string }>;
};

export const dynamic = "force-dynamic";

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
        <p className="eyebrow">PakistanJobs Blog</p>
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
        <div className="card-panel overflow-hidden">
          <div className="grid gap-px bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-3">
            {result.items.map((post) => (
              <article key={post.id} className="flex min-h-64 flex-col bg-[var(--panel)] p-5 sm:p-6">
                <div className="flex flex-wrap gap-2 text-xs text-[var(--muted)]">
                  <span>{formatDate(post.published_at || post.created_at)}</span>
                  {post.category && <span>· {post.category}</span>}
                </div>
                <h2 className="mt-3 text-xl font-semibold leading-snug text-[var(--navy-100)]">
                  <Link href={`/blog/${post.slug}`} className="hover:text-[var(--accent)]">{post.title}</Link>
                </h2>
                <p className="mt-3 line-clamp-4 text-sm leading-6 text-[var(--navy-300)]">
                  {post.excerpt || stripHtml(post.content).slice(0, 220)}
                </p>
                {post.tags.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {post.tags.slice(0, 4).map((tag) => <span key={tag} className="tag tag-blue">{tag}</span>)}
                  </div>
                )}
                <Link href={`/blog/${post.slug}`} className="mt-auto pt-5 text-sm font-semibold text-[var(--accent)]">
                  Read article →
                </Link>
              </article>
            ))}
          </div>
          <Pagination page={result.page} pages={result.pages} total={result.total} query={query} basePath="/blog" itemLabel="post" />
        </div>
      ) : (
        <div className="card-panel p-8 text-center text-[var(--muted)]">
          No blog posts matched these filters.
        </div>
      )}
    </div>
  );
}
