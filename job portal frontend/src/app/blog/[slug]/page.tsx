import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { BlogPostArticle } from "@/components/BlogPostArticle";
import {
  fetchBuildBlogPost,
  fetchBuildBlogPosts,
  fetchBuildBranding,
  fetchBuildPublicSeo,
} from "@/lib/api";
import { decodeHtmlEntities, stripHtml } from "@/lib/format";
import {
  compactSocialDescription,
  firstRichTextImage,
  selectSocialImage,
} from "@/lib/socialMetadata";

type Props = { params: Promise<{ slug: string }> };

// Keep published articles available as build-time HTML. Azure's managed Next
// runtime has intermittently failed while regenerating these pages, so live
// admin changes are applied by the hydrated article component instead.
export const dynamic = "force-static";
export const revalidate = false;

export async function generateStaticParams() {
  const firstPage = await fetchBuildBlogPosts({ page: 1, page_size: 50 });
  const remainingPages = await Promise.all(
    Array.from({ length: Math.max(0, firstPage.pages - 1) }, (_, index) =>
      fetchBuildBlogPosts({ page: index + 2, page_size: 50 }),
    ),
  );
  return [firstPage, ...remainingPages]
    .flatMap((result) => result.items)
    .map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = await fetchBuildBlogPost(slug);
  if (!post) return { title: "Blog post not found" };
  const [branding, seo] = await Promise.all([
    fetchBuildBranding(),
    fetchBuildPublicSeo("blog", post.id),
  ]);
  const canonicalPath = `/blog/${post.slug}`;
  const description =
    compactSocialDescription(seo?.meta_description || "") ||
    compactSocialDescription(post.excerpt || stripHtml(post.content));
  const pageTitle =
    decodeHtmlEntities(seo?.meta_title?.trim() || `${post.title} | ${branding.site_name}`);
  const socialTitle =
    decodeHtmlEntities(seo?.og_title?.trim() || seo?.meta_title?.trim() || post.title);
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
      authors: post.author ? [decodeHtmlEntities(post.author)] : undefined,
      images: [{ url: socialImage, alt: decodeHtmlEntities(post.title) }],
    },
    twitter: {
      card: "summary_large_image",
      title: socialTitle,
      description: socialDescription,
      images: [{ url: socialImage, alt: decodeHtmlEntities(post.title) }],
    },
  };
}

export default async function BlogPostPage({ params }: Props) {
  const { slug } = await params;
  const post = await fetchBuildBlogPost(slug);
  if (!post) notFound();
  const relatedResult = await fetchBuildBlogPosts({ category: post.category || undefined, tag: post.tags[0], page: 1, page_size: 5 });
  const related = relatedResult.items.filter((item) => item.id !== post.id).slice(0, 4);
  return <BlogPostArticle initialPost={post} initialRelated={related} />;
}
