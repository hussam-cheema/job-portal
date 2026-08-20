import { JobTaxonomyDirectoryPage, jobTaxonomyDirectoryMetadata } from "@/components/JobTaxonomyDirectoryPage";

export const dynamic = "force-dynamic";
export function generateMetadata() { return jobTaxonomyDirectoryMetadata("provinces"); }
export default function JobsByProvincesPage() { return <JobTaxonomyDirectoryPage kind="provinces" />; }
