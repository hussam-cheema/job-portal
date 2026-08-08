import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { JobShareButtons } from "@/components/JobShareButtons";
import { fetchBlogPost, fetchBlogPosts, fetchBranding, fetchPublicSeo } from "@/lib/api";
import { formatDate, stripHtml } from "@/lib/format";
import { wrapRichTextTables } from "@/lib/richText";
import { toSeoSlug } from "@/lib/slug";
import {
  compactSocialDescription,
  firstRichTextImage,
  selectSocialImage,
} from "@/lib/socialMetadata";

type Props = { params: Promise<{ slug: string }> };

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = await fetchBlogPost(slug);
  if (!post) return { title: "Blog post not found" };
  const [branding, seo] = await Promise.all([
    fetchBranding(),
    fetchPublicSeo("blog", post.id),
  ]);
  const canonicalPath = `/blog/${post.slug}`;
  const description =
    compactSocialDescription(seo?.meta_description || "") ||
    compactSocialDescription(post.excerpt || stripHtml(post.content));
  const pageTitle =
    seo?.meta_title?.trim() || `${post.title} | ${branding.site_name}`;
  const socialTitle =
    seo?.og_title?.trim() || seo?.meta_title?.trim() || post.title;
  const socialDescription =
    compactSocialDescription(seo?.og_description || "") || description;
  const socialImage = selectSocialImage(
    seo?.og_image,
    firstRichTextImage(post.content),
    branding.logo_url,
  );

  return {
    title: { absolute: pageTitle },
    description,
    keywords: seo?.meta_keywords
      ?.split(",")
      .map((keyword) => keyword.trim())
      .filter(Boolean),
    alternates: { canonical: canonicalPath },
    robots: { index: true, follow: true },
    openGraph: {
      title: socialTitle,
      description: socialDescription,
      type: "article",
      url: canonicalPath,
      siteName: branding.site_name,
      publishedTime: post.published_at || post.created_at || undefined,
      modifiedTime: post.updated_at || undefined,
      authors: post.author ? [post.author] : undefined,
      images: [{ url: socialImage, alt: post.title }],
    },
    twitter: {
      card: "summary_large_image",
      title: socialTitle,
      description: socialDescription,
      images: [{ url: socialImage, alt: post.title }],
    },
  };
}

export default async function BlogPostPage({ params }: Props) {
  const { slug } = await params;
  const post = await fetchBlogPost(slug);
  if (!post) notFound();
  const relatedResult = await fetchBlogPosts({ category: post.category || undefined, tag: post.tags[0], page: 1, page_size: 5 });
  const related = relatedResult.items.filter((item) => item.id !== post.id).slice(0, 4);
  return (
    <div className="site-wrap blog-detail-wrap py-8 sm:py-12">
      <Link href="/blog" className="text-sm text-[var(--muted)] hover:text-[var(--accent)]">← All blog posts</Link>
      <article className="card-panel mt-6 min-w-0 overflow-hidden">
        <header className="min-w-0 border-b border-[var(--border)] px-5 py-7 sm:px-9 sm:py-9">
          <div className="flex flex-wrap gap-2 text-sm text-[var(--muted)]">
            <span>{formatDate(post.published_at || post.created_at)}</span>
            {post.author && <span>· By {post.author}</span>}
            {post.category && <span>· <Link href={`/blog/categories/${toSeoSlug(post.category)}`} className="hover:text-[var(--accent)]">{post.category}</Link></span>}
          </div>
          <h1 className="mt-3 break-words text-3xl font-semibold leading-tight tracking-tight text-[var(--navy-100)] sm:text-4xl">{post.title}</h1>
          {post.excerpt && <p className="mt-4 break-words text-lg leading-7 text-[var(--navy-300)]">{post.excerpt}</p>}
          <JobShareButtons path={`/blog/${post.slug}`} title={post.title} entityLabel="post" />
        </header>
        <div className="min-w-0 px-5 py-7 sm:px-9 sm:py-9">
          <div
            className="prose-job blog-content min-w-0 max-w-full"
            dangerouslySetInnerHTML={{ __html: wrapRichTextTables(post.content) }}
          />
          {post.tags.length > 0 && (
            <div className="mt-8 flex flex-wrap gap-2 border-t border-[var(--border)] pt-5">
              {post.tags.map((tag) => <Link key={tag} href={`/blog/tags/${toSeoSlug(tag)}`} className="tag tag-blue">{tag}</Link>)}
            </div>
          )}
          <section className="mt-10 border-t border-[var(--border)] pt-7">
            <h2 className="text-xl font-semibold text-[var(--navy-100)]">Continue exploring</h2>
            {related.length > 0 && <ul className="mt-4 grid gap-2 sm:grid-cols-2">{related.map((item) => <li key={item.id}><Link href={`/blog/${item.slug}`} className="text-sm text-[var(--accent)] hover:underline">{item.title}</Link></li>)}</ul>}
            <div className="mt-5 flex flex-wrap gap-2"><Link href="/" className="btn btn-ghost">Latest jobs</Link><Link href="/resume-builder" className="btn btn-ghost">ATS Resume Builder</Link><Link href="/cover-letter" className="btn btn-ghost">Cover Letter Builder</Link><Link href="/browse" className="btn btn-ghost">Site directory</Link></div>
          </section>
        </div>
      </article>
    </div>
  );
}
