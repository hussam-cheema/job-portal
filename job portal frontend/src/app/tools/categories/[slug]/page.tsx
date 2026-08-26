import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchPublicSeo, fetchToolCategory } from "@/lib/api";
import { stripHtml } from "@/lib/format";
import { wrapRichTextTables } from "@/lib/richText";

type Props = { params: Promise<{ slug: string }> };
export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const category = await fetchToolCategory(slug);
  if (!category) return { title: "Tool category not found" };
  const seo = await fetchPublicSeo("tool_category", category.id);
  return {
    title: { absolute: seo?.meta_title || `${category.title} | Pakistan Jobs Market` },
    description: seo?.meta_description || stripHtml(category.content),
    keywords: seo?.meta_keywords?.split(",").map((value) => value.trim()).filter(Boolean),
    alternates: { canonical: `/tools/categories/${category.slug}` },
    robots: { index: true, follow: true },
  };
}

export default async function ToolCategoryPage({ params }: Props) {
  const { slug } = await params;
  const category = await fetchToolCategory(slug);
  if (!category) notFound();
  return <div className="site-wrap py-8 sm:py-12">
    <Link href="/tools" className="text-sm text-[var(--muted)] hover:text-[var(--accent)]">← All tools</Link>
    <header className="tool-detail-hero"><p className="tool-kicker">Tool category</p><h1>{category.title}</h1>{category.content && <div className="prose-job" dangerouslySetInnerHTML={{ __html: wrapRichTextTables(category.content) }} />}</header>
    <section className="tool-category-grid" aria-label={`${category.title} tools`}>
      {category.tools.length ? category.tools.map((tool) => <Link className="tool-directory-card" key={tool.id} href={`/tools/${tool.slug}`}><span>{tool.tool_kind === "content" ? "Utility" : "Interactive calculator"}</span><h2>{tool.title}</h2><p>{stripHtml(tool.content) || "Open this tool"}</p><strong>Open tool →</strong></Link>) : <div className="card-panel p-8 text-[var(--muted)]">Tools in this category are coming soon.</div>}
    </section>
  </div>;
}
