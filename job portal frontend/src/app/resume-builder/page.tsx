import type { Metadata } from "next";
import { ResumeBuilder } from "@/components/ResumeBuilder";

export const metadata: Metadata = {
  title: "Free Resume Builder",
  description:
    "Create a clean, professional resume online and download it as a PDF.",
};

export default function ResumeBuilderPage() {
  return <ResumeBuilder />;
}
