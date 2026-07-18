import type { Metadata } from "next";
import { CoverLetterBuilder } from "@/components/CoverLetterBuilder";

export const metadata: Metadata = {
  title: "Free Cover Letter Builder",
  description: "Create a professional cover letter online and download it as a PDF.",
};

export default function CoverLetterPage() {
  return <CoverLetterBuilder />;
}
