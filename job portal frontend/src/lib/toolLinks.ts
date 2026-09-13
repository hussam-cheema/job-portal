import type { ToolPage } from "@/lib/types";

export function publicToolHref(tool: Pick<ToolPage, "slug" | "tool_kind">) {
  if (tool.tool_kind === "resume_builder") return "/tools/resume-builder";
  if (tool.tool_kind === "cover_letter") return "/tools/cover-letter";
  return `/tools/${tool.slug}`;
}

export function toolExperienceLabel(tool: Pick<ToolPage, "tool_kind">) {
  if (tool.tool_kind === "resume_builder" || tool.tool_kind === "cover_letter") {
    return "Application builder";
  }
  if (tool.tool_kind === "content") return "Utility";
  if (tool.tool_kind === "document_converter") return "Document utility";
  if (tool.tool_kind === "image_watermark") return "Image editor";
  if (tool.tool_kind === "student_api") return "Developer API";
  return "Interactive calculator";
}
