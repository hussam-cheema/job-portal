import { BlogDirectoryList } from "@/components/BlogDirectoryList";
import { fetchBlogFilters, fetchBlogPosts } from "@/lib/api";
import { labelFromSlug, toSeoSlug } from "@/lib/slug";

export const dynamic = "force-dynamic";
export const revalidate = 0;
type Props = { params: Promise<{ tag: string }> };
export async function generateMetadata({ params }: Props) {
  const { tag } = await params;
  const filters = await fetchBlogFilters();
  const label =
    filters.tags.find((value) => toSeoSlug(value) === tag) ||
    labelFromSlug(tag);
  const posts = await fetchBlogPosts({ tag: label, page_size: 1 });
  return {
    title: `${label} Articles and Guides`,
    description: `Read career advice about ${label} in Pakistan.`,
    alternates: { canonical: `/blog/tags/${tag}` },
    robots: { index: posts.total > 0, follow: true },
  };
}
export default async function Page({ params }: Props) { const { tag: raw } = await params; const filters = await fetchBlogFilters(); const tag = filters.tags.find((value) => toSeoSlug(value) === raw) || labelFromSlug(raw); return <BlogDirectoryList title={`${tag} articles`} tag={tag} />; }
