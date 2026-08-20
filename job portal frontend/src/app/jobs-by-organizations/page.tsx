import { JobTaxonomyDirectoryPage, jobTaxonomyDirectoryMetadata } from "@/components/JobTaxonomyDirectoryPage";

export const dynamic = "force-dynamic";
export function generateMetadata() { return jobTaxonomyDirectoryMetadata("organizations"); }
export default function JobsByOrganizationsPage() { return <JobTaxonomyDirectoryPage kind="organizations" />; }
