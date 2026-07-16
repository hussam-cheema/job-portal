import type { Metadata } from "next";
import { ManagedPage } from "@/components/ManagedPage";

export const metadata: Metadata = {
  title: "Privacy Policy | PakistanJobs — Pakistan Job Portal",
  description: "How PakistanJobs handles public job listings, contact messages, and technical logs.",
  alternates: { canonical: "/privacy" },
  robots: { index: true, follow: true },
};

const FALLBACK = `
  <p>PakistanJobs displays publicly available job advertisements collected from third-party sources, including newspapers, company sites, and government portals.</p>
  <p>We do not sell personal data. If you contact us, we use your message only to respond. Server logs may include standard technical data for security and reliability.</p>
  <p>Job listings may include employer contact details published by the source. Use those details only for legitimate applications.</p>
`;

export default function PrivacyPage() {
  return (
    <ManagedPage slug="privacy" fallbackTitle="Privacy Policy" fallbackContent={FALLBACK} />
  );
}
