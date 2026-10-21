import type { Metadata } from "next";
import { ManagedPage } from "@/components/ManagedPage";

export const metadata: Metadata = {
  title: { absolute: "About Pakistan Jobs Market | Jobs in Pakistan" },
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
  <p><strong>Last updated:</strong> 21 October 2026</p>
  <h2>Helping people find jobs in Pakistan</h2>
  <p>We organize opportunities from employer career pages, government institutions, public service commissions and established Pakistani newspapers so visitors can browse latest jobs in Pakistan by city, job type and category.</p>
  <h2>What we offer</h2>
  <ul><li>Organized listings with source and deadline details.</li><li>Filters for cities, categories and government or private employment.</li><li>New-job email alerts, career articles, an ATS-standard resume builder with an on-page readiness score, and a cover-letter builder.</li><li>Supplementary interview Q&amp;A on selected job pages.</li></ul>
  <h2>ATS-standard resume tools</h2>
  <p>Our Resume Builder uses conventional headings, searchable text, a clean single-column reading order and recruiter-friendly formatting. Visitors can check a transparent ATS-readiness score for the resume currently in the form, review category-level feedback, and download the same professional layout as a searchable PDF or editable Word document.</p>
  <h2>How listings and supplementary answers are prepared</h2>
  <p>Directory pages group related opportunities by category, city, province, employer and newspaper. Some job pages also include supplementary interview questions and answers prepared with automated language tools from publicly available video transcripts or comments. This material can be incomplete or subjective and is never official recruitment guidance.</p>
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
