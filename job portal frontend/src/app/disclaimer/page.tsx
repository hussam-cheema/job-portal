import type { Metadata } from "next";
import { ManagedPage } from "@/components/ManagedPage";

export const metadata: Metadata = {
  title: { absolute: "Job Listing Disclaimer | Pakistan Jobs Market" },
  description: "Read the Pakistan Jobs Market disclaimer covering aggregated job advertisements, source verification, applications, external links and career tools.",
  keywords: [
    "Pakistan Jobs Market disclaimer",
    "job advertisement disclaimer",
    "Pakistan job listings",
    "newspaper jobs disclaimer",
    "recruitment fraud warning",
  ],
  alternates: { canonical: "/disclaimer" },
  robots: { index: true, follow: true },
};

const DISCLAIMER = `
  <p><strong>Pakistan Jobs Market</strong> aggregates job advertisements from public sources in good faith, including leading Pakistani newspapers, government institutions, public service commissions and private-company career pages.</p>
  <p><strong>Last updated:</strong> 21 October 2026</p>
  <h2>Not an employer or recruitment agency</h2><p>We are not the employer, testing authority or recruiting organization behind third-party vacancies and do not participate in selection, interviews, appointments or payment collection.</p>
  <h2>Verify every advertisement</h2><p>Listings may be summarized, formatted or transcribed for readability. Deadlines, eligibility, fees and procedures can change. Users must confirm every detail through the official advertisement or recruiting body; the official source always controls.</p>
  <h2>Applications, payments and fraud</h2><p>Use only official application and payment channels. Pakistan Jobs Market never guarantees employment and does not authorize anyone to request passwords, one-time codes or banking credentials in its name.</p>
  <h2>External links and automated content</h2><p>Employer, newspaper, video and application links are provided for convenience and remain outside our control. Interview Q&amp;A organized with automated language tools from public transcripts or comments may be incomplete or subjective and is supplementary study material, not official guidance.</p>
  <h2>Career tools and ATS score</h2><p>The Resume Builder follows common ATS-readable practices and provides an on-device readiness estimate based on completeness, standard sections, achievements, measurable impact, skills, keywords and readability. Applicant-tracking systems and job requirements vary, so the score is guidance rather than a test performed by an employer and does not guarantee parsing, shortlisting, an interview or employment. Users should tailor every resume to the official job description and review all generated documents before applying.</p>
  <h2>Corrections and rights</h2><p>Advertisements, logos and source materials may belong to their respective owners. Users and rights holders can contact us with a specific page URL for review, correction, attribution or removal.</p>
`;

export default function DisclaimerPage() {
  return (
    <ManagedPage slug="disclaimer" fallbackTitle="Disclaimer" fallbackContent={DISCLAIMER} />
  );
}
