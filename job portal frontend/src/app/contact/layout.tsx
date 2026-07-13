import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contact Us | PakJobs — Pakistan Job Portal",
  description:
    "Contact PakJobs for questions, partnerships, or listing corrections. Pakistan jobs support.",
  robots: { index: true, follow: true },
};

export default function ContactLayout({ children }: { children: React.ReactNode }) {
  return children;
}
