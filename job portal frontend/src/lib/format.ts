type CalendarDate = { year: number; month: number; day: number };

function calendarDate(value: string | null | undefined): CalendarDate | null {
  if (!value) return null;
  const text = value.trim();
  const datePrefix = text.match(/^(\d{4})-(\d{2})-(\d{2})(?:$|T)/);
  const hasExplicitZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text);

  // PostgreSQL returns our calendar fields as naive midnight timestamps. Do
  // not pass those through Date: doing so lets the server/browser timezone
  // move the selected day backwards or forwards.
  if (datePrefix && !hasExplicitZone) {
    return {
      year: Number(datePrefix[1]),
      month: Number(datePrefix[2]),
      day: Number(datePrefix[3]),
    };
  }

  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Karachi",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(parsed);
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((part) => part.type === type)?.value || 0);
  return { year: get("year"), month: get("month"), day: get("day") };
}

function calendarDateAsUtc(value: string | null | undefined): Date | null {
  const parts = calendarDate(value);
  return parts ? new Date(Date.UTC(parts.year, parts.month - 1, parts.day, 12)) : null;
}

export function formatDate(value: string | null | undefined): string {
  const d = calendarDateAsUtc(value);
  if (!d) return "—";
  return d.toLocaleDateString("en-PK", {
    timeZone: "UTC",
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateShort(value: string | null | undefined): string {
  const d = calendarDateAsUtc(value);
  if (!d) return "—";
  return d.toLocaleDateString("en-US", {
    timeZone: "UTC",
    month: "short",
    day: "2-digit",
  });
}

export function isDeadlinePast(value?: string | null): boolean {
  const deadline = calendarDate(value);
  if (!deadline) return false;
  const today = calendarDate(new Date().toISOString());
  if (!today) return false;
  const key = (date: CalendarDate) => date.year * 10000 + date.month * 100 + date.day;
  return key(deadline) < key(today);
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

const NAMED_HTML_ENTITIES: Record<string, string> = {
  amp: "&",
  apos: "'",
  quot: '"',
  lt: "<",
  gt: ">",
  nbsp: " ",
  ensp: " ",
  emsp: " ",
  ndash: "–",
  mdash: "—",
  hellip: "…",
  laquo: "«",
  raquo: "»",
  lsquo: "‘",
  rsquo: "’",
  ldquo: "“",
  rdquo: "”",
  bull: "•",
  copy: "©",
  reg: "®",
  trade: "™",
};

const HTML_ENTITY_PATTERN = /&(?:#(\d+)|#x([0-9a-f]+)|([a-z][a-z0-9]+));/gi;

function decodeHtmlEntitiesOnce(value: string): string {
  return value.replace(
    HTML_ENTITY_PATTERN,
    (entity, decimal: string | undefined, hexadecimal: string | undefined, named: string | undefined) => {
      if (named) return NAMED_HTML_ENTITIES[named.toLowerCase()] ?? entity;
      const codePoint = Number.parseInt(decimal || hexadecimal || "", hexadecimal ? 16 : 10);
      if (
        !Number.isFinite(codePoint) ||
        codePoint < 0 ||
        codePoint > 0x10ffff ||
        (codePoint >= 0xd800 && codePoint <= 0xdfff)
      ) {
        return entity;
      }
      return String.fromCodePoint(codePoint);
    },
  );
}

/**
 * Decode text that may have passed through more than one HTML encoder.
 *
 * Callers render the result as a React text node, so decoded angle brackets
 * remain text and cannot become executable markup.
 */
export function decodeHtmlEntities(value: string | null | undefined): string {
  let decoded = value || "";
  for (let pass = 0; pass < 4; pass += 1) {
    const next = decodeHtmlEntitiesOnce(decoded);
    if (next === decoded) break;
    decoded = next;
  }
  return decoded;
}

export function stripHtml(text: string | null | undefined): string {
  if (!text) return "";
  return decodeHtmlEntities(text.replace(/<[^>]+>/g, " "))
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
  const parts = calendarDate(value);
  if (!parts) return value?.slice(0, 10) || "";
  return `${parts.year}-${String(parts.month).padStart(2, "0")}-${String(parts.day).padStart(2, "0")}`;
}

export function dateInputToApiValue(value?: string | null): string | null {
  if (!value) return null;
  // Send a timezone-free calendar value. The database column is deliberately
  // timezone-free, so this preserves exactly what the administrator selected.
  return `${value.slice(0, 10)}T00:00:00`;
}

export function todayInPakistan(): string {
  return toDateInputValue(new Date().toISOString());
}
