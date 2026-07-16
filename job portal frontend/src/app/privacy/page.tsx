import type { Metadata } from "next";
import { ManagedPage } from "@/components/ManagedPage";

export const metadata: Metadata = {
  title: "Privacy Policy | PakistanJobs — Pakistan Job Portal",
  description: "How PakistanJobs handles public job listings, contact messages, and technical logs.",
  alternates: { canonical: "/privacy" },
  robots: { index: true, follow: true },
};

const FALLBACK = `
  <p>PakistanJobs displays publicly available job advertisements collected from third-party sources.</p>
  <p>We do not sell personal data. Contact messages are used only to respond to your inquiry.</p>
`;

export default function PrivacyPage() {
  return (
    <ManagedPage slug="privacy" fallbackTitle="Privacy Policy" fallbackContent={FALLBACK} />
  );
}
