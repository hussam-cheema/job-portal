"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { JobShareButtons } from "@/components/JobShareButtons";
import { fetchBlogPost, fetchBlogPosts } from "@/lib/api";
import { decodeHtmlEntities, formatDate } from "@/lib/format";
import { wrapRichTextTables } from "@/lib/richText";
import { toSeoSlug } from "@/lib/slug";
import type { BlogPost } from "@/lib/types";

type Props = {
  initialPost: BlogPost;
  initialRelated: BlogPost[];
};

export function BlogPostArticle({ initialPost, initialRelated }: Props) {
  const [post, setPost] = useState(initialPost);
  const [related, setRelated] = useState(initialRelated);

  useEffect(() => {
    let active = true;

    async function refreshArticle() {
      const latestPost = await fetchBlogPost(initialPost.slug);
      if (!active || !latestPost) return;

      setPost(latestPost);
      const latestRelated = await fetchBlogPosts({
        category: latestPost.category || undefined,
        tag: latestPost.tags[0],
        page: 1,
        page_size: 5,
      });
      if (!active) return;
      setRelated(
        latestRelated.items.filter((item) => item.id !== latestPost.id).slice(0, 4),
      );
    }

    void refreshArticle();
    return () => {
      active = false;
    };
  }, [initialPost.slug]);

  return (
    <div className="site-wrap blog-detail-wrap py-8 sm:py-12">
      <Link href="/blog" className="text-sm text-[var(--muted)] hover:text-[var(--accent)]">
        ← All blog posts
      </Link>
      <article className="card-panel mt-6 min-w-0 overflow-hidden">
        <header className="min-w-0 border-b border-[var(--border)] px-5 py-7 sm:px-9 sm:py-9">
          <div className="flex flex-wrap gap-2 text-sm text-[var(--muted)]">
            <span>{formatDate(post.published_at || post.created_at)}</span>
            {post.author && <span>· By {decodeHtmlEntities(post.author)}</span>}
            {post.category && (
              <span>
                ·{" "}
                <Link
                  href={`/blog/categories/${toSeoSlug(post.category)}`}
                  className="hover:text-[var(--accent)]"
                >
                  {decodeHtmlEntities(post.category)}
                </Link>
              </span>
            )}
          </div>
          <h1 className="mt-3 break-words text-3xl font-semibold leading-tight tracking-tight text-[var(--navy-100)] sm:text-4xl">
            {decodeHtmlEntities(post.title)}
          </h1>
          {post.excerpt && (
            <p className="mt-4 break-words text-lg leading-7 text-[var(--navy-300)]">
              {decodeHtmlEntities(post.excerpt)}
            </p>
          )}
          <JobShareButtons
            path={`/blog/${post.slug}`}
            title={decodeHtmlEntities(post.title)}
            entityLabel="post"
          />
        </header>
        <div className="min-w-0 px-5 py-7 sm:px-9 sm:py-9">
          <div
            className="prose-job blog-content min-w-0 max-w-full"
            dangerouslySetInnerHTML={{ __html: wrapRichTextTables(post.content) }}
          />
          {post.tags.length > 0 && (
            <div className="mt-8 flex flex-wrap gap-2 border-t border-[var(--border)] pt-5">
              {post.tags.map((tag) => (
                <Link
                  key={tag}
                  href={`/blog/tags/${toSeoSlug(tag)}`}
                  className="tag tag-blue"
                >
                  {decodeHtmlEntities(tag)}
                </Link>
              ))}
            </div>
          )}
          <section className="mt-10 border-t border-[var(--border)] pt-7">
            <h2 className="text-xl font-semibold text-[var(--navy-100)]">
              Continue exploring
            </h2>
            {related.length > 0 && (
              <ul className="mt-4 grid gap-2 sm:grid-cols-2">
                {related.map((item) => (
                  <li key={item.id}>
                    <Link
                      href={`/blog/${item.slug}`}
                      className="text-sm text-[var(--accent)] hover:underline"
                    >
                      {decodeHtmlEntities(item.title)}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-5 flex flex-wrap gap-2">
              <Link href="/" className="btn btn-ghost">Latest jobs</Link>
              <Link href="/tools/resume-builder" className="btn btn-ghost">ATS Resume Builder</Link>
              <Link href="/tools/cover-letter" className="btn btn-ghost">Cover Letter Builder</Link>
              <Link href="/browse" className="btn btn-ghost">Site directory</Link>
            </div>
          </section>
        </div>
      </article>
    </div>
  );
}
