export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-PK", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateShort(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { month: "short", day: "2-digit" });
}

export function formatSalary(
  min: number | null | undefined,
  max: number | null | undefined,
  currency = "PKR",
  rangeText?: string | null
): string | null {
  if (rangeText) return rangeText;
  if (min == null && max == null) return null;
  const fmt = (n: number) => (n >= 1000 ? `${Math.round(n / 1000)}k` : String(n));
  if (min != null && max != null) return `${currency} ${fmt(min)}–${fmt(max)}`;
  if (min != null) return `${currency} ${fmt(min)}+`;
  return `${currency} up to ${fmt(max!)}`;
}

export function labelSource(type: string): string {
  const map: Record<string, string> = {
    newspaper: "Newspaper",
    company: "Private",
    private: "Private",
    govt: "Government",
    government: "Government",
  };
  return map[type] || type;
}

export function labelEmployment(type: string | null | undefined): string {
  if (!type) return "—";
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function sourceBadgeClass(type: string): string {
  switch (type) {
    case "govt":
    case "government":
      return "tag-gold";
    case "company":
    case "private":
      return "tag-blue";
    case "newspaper":
      return "tag-green";
    default:
      return "tag-slate";
  }
}

const TAG_PALETTE = [
  "tag-blue",
  "tag-violet",
  "tag-cyan",
  "tag-rose",
  "tag-amber",
  "tag-green",
  "tag-indigo",
  "tag-orange",
];

export function tagColorClass(label: string): string {
  const key = label.toLowerCase();
  if (key === "government" || key === "govt") return "tag-gold";
  if (key === "private") return "tag-blue";
  if (key === "newspaper") return "tag-green";
  let hash = 0;
  for (let i = 0; i < label.length; i++) hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  return TAG_PALETTE[hash % TAG_PALETTE.length];
}

export function stripHtml(text: string | null | undefined): string {
  if (!text) return "";
  return text
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ")
    .trim();
}

export function summarize(text: string | null | undefined, max = 280): string {
  if (!text) return "No summary available for this listing yet.";
  const clean = stripHtml(text);
  if (clean.length <= max) return clean;
  return clean.slice(0, max).trimEnd() + "…";
}

export function slugTag(tag: string): string {
  return encodeURIComponent(tag);
}

export function toDateInputValue(value?: string | null): string {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value.slice(0, 10);
  return d.toISOString().slice(0, 10);
}
