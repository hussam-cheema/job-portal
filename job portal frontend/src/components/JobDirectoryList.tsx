import Link from "next/link";
import { JobCard } from "@/components/JobCard";
import { Pagination } from "@/components/Pagination";
import { fetchJobs } from "@/lib/api";
import type { JobQuery } from "@/lib/types";

export async function JobDirectoryList({
  title,
  eyebrow,
  query,
  page = 1,
  basePath,
}: {
  title: string;
  eyebrow: string;
  query: JobQuery;
  page?: number;
  basePath?: string;
}) {
  const data = await fetchJobs({ ...query, page, page_size: 30 });
  const paginationQuery = Object.fromEntries(
    Object.entries(query).filter(
      (entry): entry is [string, string] => typeof entry[1] === "string" && Boolean(entry[1]),
    ),
  );
  return (
    <div className="site-wrap py-10">
      <Link href="/browse" className="mb-6 inline-flex text-sm text-[var(--muted)] hover:text-[var(--accent)]">← Browse all</Link>
      <header className="mb-7">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-2 text-3xl font-semibold text-[var(--navy-100)]">{title}</h1>
        <p className="mt-2 text-[var(--muted)]">{data.total} related opening{data.total === 1 ? "" : "s"}</p>
      </header>
      <section className="card-panel">
        {data.items.length ? <div className="job-list">{data.items.map((job) => <JobCard key={job.id} job={job} />)}</div> : <p className="p-10 text-center text-[var(--muted)]">No matching jobs are published yet.</p>}
        <Pagination page={data.page} pages={data.pages} total={data.total} query={paginationQuery} basePath={basePath} />
      </section>
    </div>
  );
}
