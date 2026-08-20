import { JobTaxonomyDirectoryPage, jobTaxonomyDirectoryMetadata } from "@/components/JobTaxonomyDirectoryPage";

export const dynamic = "force-dynamic";
export function generateMetadata() { return jobTaxonomyDirectoryMetadata("cities"); }
export default function JobsByCitiesPage() { return <JobTaxonomyDirectoryPage kind="cities" />; }
