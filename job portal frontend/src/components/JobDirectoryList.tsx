import Link from "next/link";
import { JobCard } from "@/components/JobCard";
import { fetchJobs } from "@/lib/api";
import type { JobQuery } from "@/lib/types";

export async function JobDirectoryList({ title, eyebrow, query }: { title: string; eyebrow: string; query: JobQuery }) {
  const data = await fetchJobs({ ...query, page: 1, page_size: 50 });
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
      </section>
    </div>
  );
}
