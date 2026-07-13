import Link from "next/link";

export default function NotFound() {
  return (
    <div className="site-wrap py-24 text-center">
      <h1 className="text-2xl font-semibold text-white">Job not found</h1>
      <p className="mt-2 text-[var(--muted)]">This listing may have been removed.</p>
      <Link href="/" className="btn btn-primary mt-6 inline-flex">
        Back to issues
      </Link>
    </div>
  );
}
