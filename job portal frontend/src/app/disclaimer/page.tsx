import type { Metadata } from "next";
import { ManagedPage } from "@/components/ManagedPage";

export const metadata: Metadata = {
  title: "Disclaimer | PakistanJobs",
  description: "PakistanJobs job advertisement aggregation disclaimer.",
  alternates: { canonical: "/disclaimer" },
  robots: { index: true, follow: true },
};

const DISCLAIMER = `
  <p><strong>PakistanJobs</strong> aggregates job advertisements from Pakistan's leading newspapers, including <em>Daily Jang</em>, <em>Express</em>, <em>Nawa-i-Waqt</em>, <em>The News</em>, <em>Dawn</em>, <em>The Nation</em>, and others, as well as from the careers and jobs pages of government institutions and private companies. Our goal is to support job seekers across cities such as Karachi, Lahore, Rawalpindi, Islamabad, Peshawar, and beyond by bringing together newspaper listings and both private- and public-sector job postings in one place. This service is offered in good faith as a public resource, and we are not responsible for any advertisement that is inaccurate, misrepresented, or misleading.</p>
`;

export default function DisclaimerPage() {
  return (
    <ManagedPage slug="disclaimer" fallbackTitle="Disclaimer" fallbackContent={DISCLAIMER} />
  );
}
