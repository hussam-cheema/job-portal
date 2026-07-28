import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contact Pakistan Jobs Market | Support & Corrections",
  description:
    "Contact Pakistan Jobs Market for job-listing corrections, partnerships, privacy questions, technical support, or general feedback.",
  keywords: [
    "contact Pakistan Jobs Market",
    "Pakistan jobs support",
    "job listing correction Pakistan",
  ],
  alternates: { canonical: "/contact" },
  robots: { index: true, follow: true },
};

export default function ContactLayout({ children }: { children: React.ReactNode }) {
  return children;
}
