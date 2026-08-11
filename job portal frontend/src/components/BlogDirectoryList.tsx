import Link from "next/link";
import { fetchBlogPosts } from "@/lib/api";
import { decodeHtmlEntities, formatDate, stripHtml } from "@/lib/format";

export async function BlogDirectoryList({ title, category, tag }: { title: string; category?: string; tag?: string }) {
  const data = await fetchBlogPosts({ category, tag, page: 1, page_size: 50 });
  return (
    <div className="site-wrap py-8 sm:py-12">
      <Link href="/blog" className="text-sm text-[var(--muted)] hover:text-[var(--accent)]">← All career guides</Link>
      <header className="my-7"><p className="eyebrow">Career guidance</p><h1 className="mt-2 text-3xl font-semibold text-[var(--navy-100)]">{title}</h1></header>
      <div className="grid gap-4">
        {data.items.map((post) => (
          <article key={post.id} className="card-panel p-5 sm:p-7">
            <time className="text-xs text-[var(--muted)]">{formatDate(post.published_at || post.created_at)}</time>
            <h2 className="mt-2 text-xl font-semibold text-[var(--navy-100)]"><Link href={`/blog/${post.slug}`} className="hover:text-[var(--accent)]">{decodeHtmlEntities(post.title)}</Link></h2>
            <p className="mt-2 line-clamp-3 text-sm leading-6 text-[var(--navy-300)]">{decodeHtmlEntities(post.excerpt || stripHtml(post.content).slice(0, 260))}</p>
          </article>
        ))}
        {!data.items.length && <p className="card-panel p-10 text-center text-[var(--muted)]">No matching guides are published yet.</p>}
      </div>
    </div>
  );
}
