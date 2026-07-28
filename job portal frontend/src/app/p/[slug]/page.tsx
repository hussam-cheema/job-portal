import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchPage, fetchPublicSeo } from "@/lib/api";
import { stripHtml } from "@/lib/format";

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
  const description =
    seo?.meta_description ||
    stripHtml(page.content).replace(/\s+/g, " ").trim().slice(0, 160);

  return {
    title: seo?.meta_title || page.title,
    description,
    keywords: seo?.meta_keywords
      ?.split(",")
      .map((keyword) => keyword.trim())
      .filter(Boolean),
    alternates: { canonical: `/p/${slug}` },
    robots: { index: true, follow: true },
    openGraph: {
      title: seo?.og_title || seo?.meta_title || page.title,
      description: seo?.og_description || description,
      type: "article",
      url: `/p/${slug}`,
      images: seo?.og_image ? [{ url: seo.og_image }] : undefined,
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
          {page.title}
        </h1>
        <div
          className="prose-job mt-6 text-[0.95rem] leading-relaxed text-[var(--navy-200)]"
          dangerouslySetInnerHTML={{ __html: page.content }}
        />
      </article>
    </div>
  );
}
