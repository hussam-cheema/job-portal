import type { Metadata } from "next";
import { ManagedPage } from "@/components/ManagedPage";

export const metadata: Metadata = {
  title: "About Pakistan Jobs Market | Jobs in Pakistan",
  description:
    "Learn how Pakistan Jobs Market helps job seekers discover government, private, newspaper and company career opportunities across Pakistan.",
  keywords: [
    "about Pakistan Jobs Market",
    "jobs in Pakistan",
    "Pakistan job portal",
    "government jobs",
    "private jobs",
    "newspaper jobs",
    "career resources",
  ],
  alternates: { canonical: "/about" },
  robots: { index: true, follow: true },
};

const FALLBACK = `
  <p><strong>Pakistan Jobs Market</strong> is an independent job discovery platform that helps people find current government, private-sector, newspaper and company career opportunities across Pakistan.</p>
  <h2>Helping people find jobs in Pakistan</h2>
  <p>We organize opportunities from employer career pages, government institutions, public service commissions and established Pakistani newspapers so visitors can browse latest jobs in Pakistan by city, job type and category.</p>
  <h2>What we offer</h2>
  <ul><li>Organized listings with source and deadline details.</li><li>Filters for cities, categories and government or private employment.</li><li>New-job email alerts, career articles, a resume builder and a cover-letter builder.</li><li>Supplementary interview Q&amp;A on selected job pages.</li></ul>
  <h2>Our editorial approach</h2>
  <p>We aim to present clear, source-attributed information, but Pakistan Jobs Market is not a recruitment agency. Candidates should always verify eligibility, deadlines, fees and application instructions against the official advertisement.</p>
  <h2>Accuracy and safe job searching</h2>
  <p>Recruitment notices can change or be withdrawn. Visitors can report outdated or inaccurate details through our Contact Us page. Never share passwords, one-time codes or banking credentials with an unverified recruiter.</p>
  <h2>Our commitment</h2>
  <p>We serve students, fresh graduates, experienced professionals and public-sector candidates throughout Pakistan, and continually improve our listings, search tools and practical career guidance.</p>
`;

export default function AboutPage() {
  return <ManagedPage slug="about" fallbackTitle="About Us" fallbackContent={FALLBACK} />;
}
