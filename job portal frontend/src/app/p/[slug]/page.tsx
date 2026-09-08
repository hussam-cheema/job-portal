import { selectSocialImage } from "@/lib/socialMetadata";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchPage, fetchPublicSeo } from "@/lib/api";
import { decodeHtmlEntities, stripHtml } from "@/lib/format";
import { wrapRichTextTables } from "@/lib/richText";

type Props = {
  params: Promise<{ slug: string }>;
};

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const page = await fetchPage(slug);
  if (!page?.is_published) {
    return {
      title: "Page not found",
      robots: { index: false, follow: false },
    };
  }

  const seo = await fetchPublicSeo("page", page.id);
  const description = decodeHtmlEntities(
    seo?.meta_description ||
      stripHtml(page.content).replace(/\s+/g, " ").trim().slice(0, 160),
  );

  return {
    title: decodeHtmlEntities(seo?.meta_title || page.title),
    description,
    keywords: seo?.meta_keywords
      ?.split(",")
      .map((keyword) => keyword.trim())
      .filter(Boolean),
    alternates: { canonical: `/p/${slug}` },
    robots: { index: true, follow: true },
    openGraph: {
      title: decodeHtmlEntities(seo?.og_title || seo?.meta_title || page.title),
      description: decodeHtmlEntities(seo?.og_description || description),
      type: "article",
      url: `/p/${slug}`,
      images: [{ url: selectSocialImage(seo?.og_image) }],
    },
  };
}

export default async function PublicCmsPage({ params }: Props) {
  const { slug } = await params;
  const page = await fetchPage(slug);
  if (!page?.is_published) notFound();

  return (
    <div className="site-wrap max-w-3xl py-12">
      <Link href="/" className="text-sm text-[var(--muted)] hover:text-[var(--navy-200)]">
        ← Jobs
      </Link>
      <article>
        <h1 className="mt-6 text-3xl font-semibold text-[var(--navy-100)]">
          {decodeHtmlEntities(page.title)}
        </h1>
        <div
          className="prose-job mt-6 text-[0.95rem] leading-relaxed text-[var(--navy-200)]"
          dangerouslySetInnerHTML={{ __html: wrapRichTextTables(page.content) }}
        />
      </article>
    </div>
  );
}
