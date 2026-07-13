import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About Us | PakJobs — Pakistan Job Portal",
  description:
    "Learn about PakJobs: a modern Pakistan job portal for government and private openings with commonly asked interview QnA.",
  keywords: [
    "PakJobs",
    "Pakistan jobs",
    "about PakJobs",
    "government jobs Pakistan",
    "private jobs Pakistan",
  ],
  alternates: { canonical: "/about" },
  openGraph: {
    title: "About Us | PakJobs",
    description:
      "PakJobs lists government and private job openings across Pakistan.",
    type: "website",
    url: "/about",
  },
  robots: { index: true, follow: true },
};

export default function AboutPage() {
  return (
    <div className="site-wrap max-w-3xl py-12">
      <Link href="/" className="text-sm text-[var(--muted)] hover:text-[var(--navy-200)]">
        ← Jobs
      </Link>
      <article>
        <h1 className="mt-6 text-3xl font-semibold text-[var(--navy-100)]">About us</h1>
        <div className="mt-6 space-y-4 text-[var(--navy-200)] leading-relaxed">
          <p>
            <strong className="text-[var(--navy-100)]">PakJobs</strong> is a modern job portal for
            Pakistan. Browse curated government and private openings with city, skills, and category
            tags.
          </p>
          <p>
            Job pages include commonly asked questions and answers sourced from closely matched
            YouTube videos when verified Q&amp;A is available.
          </p>
          <p>
            Whether you are preparing for private-sector roles or public-sector competitive exams,
            PakJobs helps you discover opportunities faster.
          </p>
        </div>
      </article>
    </div>
  );
}
