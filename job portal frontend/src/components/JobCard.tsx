import type { DirectoryPageLink, JobSummary } from "@/lib/types";
import { findDirectoryPage, publicPagePath } from "@/lib/pagePath";
import { JobCardView, type JobCardData } from "./JobCardView";

// Select fields before crossing the client boundary. Full descriptions and the
// directory catalogue belong on the server, not in every interactive card.
export function JobCard({ job, directoryPages = [] }: {
  job: JobSummary;
  directoryPages?: DirectoryPageLink[];
}) {
  const {
    id, slug, title, salary_range, salary_min, salary_max, currency,
    published_date, created_at, applications_closed, deadline_date,
    application_deadline, nationwide, provinces, cities, tags, source_type,
    category, newspaper, education_required, experience_required, company,
    source, location, city, job_type,
  } = job;
  const card: JobCardData = {
    id, slug, title, salary_range, salary_min, salary_max, currency,
    published_date, created_at, applications_closed, deadline_date,
    application_deadline, nationwide, provinces, cities, tags, source_type,
    category, newspaper, education_required, experience_required, company,
    source, location, city, job_type,
  };
  const categoryPage = findDirectoryPage(directoryPages, "category", category);
  return <JobCardView job={card} categoryHref={categoryPage ? publicPagePath(categoryPage) : undefined} />;
}
