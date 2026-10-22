import type { Metadata } from "next";
import { ManagedPage } from "@/components/ManagedPage";

export const metadata: Metadata = {
  title: { absolute: "Editorial and Listing Maintenance Policy | Pakistan Jobs Market" },
  description:
    "Read how Pakistan Jobs Market selects, sources, reviews, updates and archives public job listings, career guides and supplementary interview information.",
  keywords: [
    "Pakistan Jobs Market editorial policy",
    "job listing standards Pakistan",
    "job advertisement source verification",
    "job listing corrections",
    "job archive policy",
  ],
  alternates: { canonical: "/editorial-policy" },
  robots: { index: true, follow: true },
};

const FALLBACK = `
  <p><strong>Effective date:</strong> 22 October 2026</p>
  <p>Pakistan Jobs Market publishes public recruitment information and practical career
  resources for people searching for work in Pakistan. This policy explains what we choose
  to publish, how records are maintained, and how readers can report a problem.</p>

  <h2>What we publish</h2>
  <p>We select recruitment notices from publicly accessible sources such as government
  departments, public service commissions, employer career pages and established Pakistani
  newspapers. We organize the information into searchable records and link to a reference or
  application source when one is available.</p>
  <p>A job record should identify the recruiting organization, role, location, publication
  date, application deadline and the principal eligibility and application details. We may
  correct formatting or remove unsafe embedded code, but we do not invent qualifications,
  salaries, locations or deadlines that were not provided by the source.</p>

  <h2>Search-quality standard</h2>
  <p>A job record is eligible for search when it has a named recruiting organization, a usable
  reference or application link, a recorded application deadline and a substantive description
  of at least 150 words. Active records appear in the active job sitemap. Complete records whose
  deadline has passed move automatically to the <a href="/archive">job archive</a> and its
  sitemap, with a clear archived status and without active job structured data.</p>
  <p>Records that are incomplete, unusually short or missing a verifiable source remain available
  to people who already have the link, but they are marked <code>noindex</code> and excluded
  from the sitemap. A directory page is included only when at least one search-ready active
  record belongs to that directory.</p>

  <h2>Ongoing maintenance</h2>
  <ul>
    <li>Deadline status is checked when a listing is served and when the sitemap is built.</li>
    <li>Complete closed records move to the archive sitemap and stop appearing as active jobs.</li>
    <li>Incomplete or unsourced records remain excluded from the sitemap.</li>
    <li>Each job page displays the source, deadline and the date its record was last updated.</li>
    <li>Repository and content-quality checks run before website changes are deployed.</li>
    <li>Readers can report a changed deadline, broken source link or inaccurate detail through
    the Contact page, including the affected URL.</li>
  </ul>

  <h2>Source limitations</h2>
  <p>Pakistan Jobs Market is not the recruiter and cannot approve an application, change an
  eligibility rule or extend a deadline. Advertisements may be corrected, withdrawn or
  replaced after we publish a record. The source advertisement and the recruiting organization
  always take priority. We therefore describe our pages as discovery and reference material,
  not as an official recruitment service.</p>

  <h2>Career guides and original analysis</h2>
  <p>Career guides are prepared to answer practical questions for Pakistani applicants.
  Where rules, public pay scales, tax rates or examination requirements are discussed, we
  prefer government publications, official notices, statistical agencies and the responsible
  institution. Guides show source links and dates where appropriate, distinguish confirmed
  facts from illustrative examples, and explain material limitations.</p>

  <h2>Automated assistance and interview Q&amp;A</h2>
  <p>Some job pages contain supplementary interview questions and answers organized from
  publicly available video transcripts or comments with the help of language-model tools.
  Automated material is reviewed for basic answer quality, but it can still be incomplete,
  subjective or outdated. It is study support, not an official question paper, answer key or
  recruitment instruction. It does not replace the current advertisement or the recruiting
  organization's guidance.</p>

  <h2>Independence and advertising</h2>
  <p>Editorial inclusion is based on usefulness to job seekers and the quality checks above.
  Advertising or sponsorship does not change a job's deadline, source link, eligibility facts
  or archival status. Pakistan Jobs Market does not guarantee employment and does not accept
  payment to promise an appointment.</p>

  <h2>Corrections and removal requests</h2>
  <p>If a page contains an error, send us the page URL, the information that is wrong and,
  where possible, a link to the controlling source. Rights holders may also request review of
  attribution or use of source material. We will inspect the evidence and correct, update,
  unpublish or archive the record where appropriate.</p>

  <h2>Policy updates</h2>
  <p>This policy will be updated when our publishing or maintenance process changes. The
  effective date at the top identifies the current published version.</p>

  <p>For a listing correction, use our <a href="/contact">Contact page</a>. For broader
  sourcing and accuracy context, read the <a href="/about">About page</a> and our
  <a href="/disclaimer">Disclaimer</a>. Expired historical notices remain available in the
  <a href="/archive">job archive</a>.</p>
`.trim();

export default function EditorialPolicyPage() {
  return (
    <ManagedPage
      slug="editorial-policy"
      fallbackTitle="Editorial and Listing Maintenance Policy"
      fallbackContent={FALLBACK}
    />
  );
}
