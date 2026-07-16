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
  <p><strong>PakistanJobs</strong> helps Pakistanis discover government and private job openings.</p>
  <p>Browse opportunities with city, skills, and category tags, plus verified interview questions and answers when available.</p>
`;

export default function AboutPage() {
  return <ManagedPage slug="about" fallbackTitle="About Us" fallbackContent={FALLBACK} />;
}
