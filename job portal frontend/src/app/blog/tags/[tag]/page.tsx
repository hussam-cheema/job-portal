import { BlogDirectoryList } from "@/components/BlogDirectoryList";
import { fetchBlogFilters } from "@/lib/api";
import { labelFromSlug, toSeoSlug } from "@/lib/slug";
type Props = { params: Promise<{ tag: string }> };
export async function generateMetadata({ params }: Props) { const { tag } = await params; const label = labelFromSlug(tag); return { title: `${label} Articles and Guides`, description: `Read career advice about ${label} in Pakistan.`, alternates: { canonical: `/blog/tags/${tag}` }, robots: { index: true, follow: true } }; }
export default async function Page({ params }: Props) { const { tag: raw } = await params; const filters = await fetchBlogFilters(); const tag = filters.tags.find((value) => toSeoSlug(value) === raw) || labelFromSlug(raw); return <BlogDirectoryList title={`${tag} articles`} tag={tag} />; }
