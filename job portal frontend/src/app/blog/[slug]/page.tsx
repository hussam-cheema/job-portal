import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { JobShareButtons } from "@/components/JobShareButtons";
import { fetchBlogPost } from "@/lib/api";
import { formatDate, stripHtml } from "@/lib/format";

type Props = { params: Promise<{ slug: string }> };

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = await fetchBlogPost(slug);
  if (!post) return { title: "Blog post not found" };
  const description = post.excerpt || stripHtml(post.content).slice(0, 160);
  return {
    title: post.title,
    description,
    alternates: { canonical: `/blog/${post.slug}` },
    openGraph: { title: post.title, description, type: "article" },
  };
}

export default async function BlogPostPage({ params }: Props) {
  const { slug } = await params;
  const post = await fetchBlogPost(slug);
  if (!post) notFound();
  return (
    <div className="site-wrap blog-detail-wrap py-8 sm:py-12">
      <Link href="/blog" className="text-sm text-[var(--muted)] hover:text-[var(--accent)]">← All blog posts</Link>
      <article className="card-panel mt-6 min-w-0 overflow-hidden">
        <header className="min-w-0 border-b border-[var(--border)] px-5 py-7 sm:px-9 sm:py-9">
          <div className="flex flex-wrap gap-2 text-sm text-[var(--muted)]">
            <span>{formatDate(post.published_at || post.created_at)}</span>
            {post.author && <span>· By {post.author}</span>}
            {post.category && <span>· {post.category}</span>}
          </div>
          <h1 className="mt-3 break-words text-3xl font-semibold leading-tight tracking-tight text-[var(--navy-100)] sm:text-4xl">{post.title}</h1>
          {post.excerpt && <p className="mt-4 break-words text-lg leading-7 text-[var(--navy-300)]">{post.excerpt}</p>}
          <JobShareButtons path={`/blog/${post.slug}`} title={post.title} entityLabel="post" />
        </header>
        <div className="min-w-0 px-5 py-7 sm:px-9 sm:py-9">
          <div className="prose-job blog-content min-w-0 max-w-full" dangerouslySetInnerHTML={{ __html: post.content }} />
          {post.tags.length > 0 && (
            <div className="mt-8 flex flex-wrap gap-2 border-t border-[var(--border)] pt-5">
              {post.tags.map((tag) => <Link key={tag} href={`/blog?tag=${encodeURIComponent(tag)}`} className="tag tag-blue">{tag}</Link>)}
            </div>
          )}
        </div>
      </article>
    </div>
  );
}
