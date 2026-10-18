import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CGPACalculator } from "@/components/CGPACalculator";
import { CoverLetterBuilder } from "@/components/CoverLetterBuilder";
import { PakistanTaxCalculator } from "@/components/PakistanTaxCalculator";
import { DocumentConverter } from "@/components/DocumentConverter";
import { GovernmentSalaryCalculator } from "@/components/GovernmentSalaryCalculator";
import { ImageWatermark } from "@/components/ImageWatermark";
import { ImageWatermarkRemoval } from "@/components/ImageWatermarkRemoval";
import { ResumeBuilder } from "@/components/ResumeBuilder";
import { StudentApiAccess } from "@/components/StudentApiAccess";
import { ToolUsageObserver } from "@/components/ToolUsageObserver";
import { fetchPublicSeo, fetchTool, fetchTools } from "@/lib/api";
import { stripHtml } from "@/lib/format";
import { wrapRichTextTables } from "@/lib/richText";

type Props = { params: Promise<{ slug: string }> };
export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const tool = await fetchTool(slug);
  if (!tool) return { title: "Tool not found" };
  const seo = await fetchPublicSeo("tool", tool.id);
  return {
    title: { absolute: seo?.meta_title || `${tool.title} | Pakistan Jobs Market` },
    description: seo?.meta_description || stripHtml(tool.content),
    keywords: seo?.meta_keywords?.split(",").map((value) => value.trim()).filter(Boolean),
    alternates: { canonical: `/tools/${tool.slug}` },
    robots: { index: true, follow: true },
  };
}

export default async function ToolPage({ params }: Props) {
  const { slug } = await params;
  const [tool, categories] = await Promise.all([fetchTool(slug), fetchTools()]);
  if (!tool) notFound();
  if (tool.tool_kind === "resume_builder") return <><ToolUsageObserver slug={tool.slug}><ResumeBuilder /></ToolUsageObserver>{tool.content && <section className="site-wrap card-panel tool-cms-content"><div className="prose-job" dangerouslySetInnerHTML={{ __html: wrapRichTextTables(tool.content) }} /></section>}</>;
  if (tool.tool_kind === "cover_letter") return <><ToolUsageObserver slug={tool.slug}><CoverLetterBuilder /></ToolUsageObserver>{tool.content && <section className="site-wrap card-panel tool-cms-content"><div className="prose-job" dangerouslySetInnerHTML={{ __html: wrapRichTextTables(tool.content) }} /></section>}</>;
  const category = categories.find((item) => item.id === tool.category_id);
  return <div className="site-wrap tool-page-wrap py-8 sm:py-12">
    <nav className="tool-breadcrumb" aria-label="Breadcrumb"><Link href="/tools">Tools</Link><span>›</span>{category && <><Link href={`/tools/categories/${category.slug}`}>{category.title}</Link><span>›</span></>}<span>{tool.title}</span></nav>
    <header className="tool-detail-hero"><p className="tool-kicker">Free online tool</p><h1>{tool.title}</h1></header>
    <ToolUsageObserver slug={tool.slug}>
      {tool.tool_kind === "tax_calculator" ? <PakistanTaxCalculator /> : tool.tool_kind === "government_salary_calculator" ? <GovernmentSalaryCalculator /> : tool.tool_kind === "cgpa_calculator" ? <CGPACalculator /> : tool.tool_kind === "document_converter" ? <DocumentConverter /> : tool.tool_kind === "image_watermark" ? <ImageWatermark /> : tool.tool_kind === "image_watermark_removal" ? <ImageWatermarkRemoval /> : tool.tool_kind === "student_api" ? <StudentApiAccess /> : <div className="card-panel p-8 text-[var(--muted)]">This tool&apos;s interactive experience is being prepared.</div>}
    </ToolUsageObserver>
    {tool.content && <section className="card-panel tool-cms-content"><div className="prose-job" dangerouslySetInnerHTML={{ __html: wrapRichTextTables(tool.content) }} /></section>}
  </div>;
}
