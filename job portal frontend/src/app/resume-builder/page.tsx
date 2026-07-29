import type { Metadata } from "next";
import { ResumeBuilder } from "@/components/ResumeBuilder";

export const metadata: Metadata = {
  title: "Free ATS Resume Builder and Resume Score",
  description:
    "Build an ATS-standard professional resume, check its ATS readiness score online, and download it as a searchable PDF or editable DOCX.",
  keywords: [
    "ATS resume builder Pakistan",
    "free ATS score checker",
    "professional resume builder",
    "ATS friendly CV",
    "resume PDF",
    "resume DOCX",
  ],
  alternates: { canonical: "/resume-builder" },
  robots: { index: true, follow: true },
};

export default function ResumeBuilderPage() {
  return <ResumeBuilder />;
}
