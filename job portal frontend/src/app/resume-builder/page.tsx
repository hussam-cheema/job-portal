import type { Metadata } from "next";
import { ResumeBuilder } from "@/components/ResumeBuilder";

export const metadata: Metadata = {
  title: "Free Resume Builder",
  description:
    "Create a clean, professional resume online and download it as a PDF or editable DOCX.",
};

export default function ResumeBuilderPage() {
  return <ResumeBuilder />;
}
