import { JobTaxonomyDirectoryPage, jobTaxonomyDirectoryMetadata } from "@/components/JobTaxonomyDirectoryPage";

export const dynamic = "force-dynamic";
export function generateMetadata() { return jobTaxonomyDirectoryMetadata("categories"); }
export default function JobsByCategoriesPage() { return <JobTaxonomyDirectoryPage kind="categories" />; }
