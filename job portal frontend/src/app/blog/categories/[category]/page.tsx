import { BlogDirectoryList } from "@/components/BlogDirectoryList";
import { fetchBlogFilters, fetchBlogPosts } from "@/lib/api";
import { labelFromSlug, toSeoSlug } from "@/lib/slug";

export const dynamic = "force-dynamic";
export const revalidate = 0;
type Props = { params: Promise<{ category: string }> };
export async function generateMetadata({ params }: Props) {
  const { category } = await params;
  const filters = await fetchBlogFilters();
  const label =
    filters.categories.find((value) => toSeoSlug(value) === category) ||
    labelFromSlug(category);
  const posts = await fetchBlogPosts({ category: label, page_size: 1 });
  return {
    title: `${label} Career Guides`,
    description: `Read ${label} career guides for Pakistan's job market.`,
    alternates: { canonical: `/blog/categories/${category}` },
    robots: { index: posts.total > 0, follow: true },
  };
}
export default async function Page({ params }: Props) { const { category: raw } = await params; const filters = await fetchBlogFilters(); const category = filters.categories.find((value) => toSeoSlug(value) === raw) || labelFromSlug(raw); return <BlogDirectoryList title={`${category} guides`} category={category} />; }
