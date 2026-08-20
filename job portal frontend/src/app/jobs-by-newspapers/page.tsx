import { JobTaxonomyDirectoryPage, jobTaxonomyDirectoryMetadata } from "@/components/JobTaxonomyDirectoryPage";

export const dynamic = "force-dynamic";
export function generateMetadata() { return jobTaxonomyDirectoryMetadata("newspapers"); }
export default function JobsByNewspapersPage() { return <JobTaxonomyDirectoryPage kind="newspapers" />; }
