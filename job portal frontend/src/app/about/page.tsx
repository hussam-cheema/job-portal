import type { Metadata } from "next";
import { ManagedPage } from "@/components/ManagedPage";

export const metadata: Metadata = {
  title: "About Us | PakistanJobs — Pakistan Job Portal",
  description:
    "Learn about PakistanJobs, a Pakistan job portal for government and private openings.",
  alternates: { canonical: "/about" },
  robots: { index: true, follow: true },
};

const FALLBACK = `
  <p><strong>PakistanJobs</strong> is a modern job portal for Pakistan. Browse curated government and private openings with city, skills, and category tags.</p>
  <p>Job pages include commonly asked questions and answers sourced from closely matched YouTube videos when verified Q&amp;A is available.</p>
  <p>Whether you are preparing for private-sector roles or public-sector competitive exams, PakistanJobs helps you discover opportunities faster.</p>
`;

export default function AboutPage() {
  return <ManagedPage slug="about" fallbackTitle="About Us" fallbackContent={FALLBACK} />;
}
