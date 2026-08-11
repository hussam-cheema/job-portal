const TABLE_PATTERN = /<table\b[^>]*>[\s\S]*?<\/table>/gi;
const NESTED_ENTITY_PATTERN =
  /&(?:amp;)+(#[0-9]+;|#x[0-9a-f]+;|amp;|apos;|quot;|lt;|gt;|nbsp;|ensp;|emsp;|ndash;|mdash;|hellip;|laquo;|raquo;|lsquo;|rsquo;|ldquo;|rdquo;|bull;|copy;|reg;|trade;)/gi;

/**
 * Collapse only nested entity escaping (for example `&amp;#39;` -> `&#39;`).
 * This deliberately does not fully unescape rich HTML before it is inserted:
 * escaped angle brackets therefore remain text instead of becoming markup.
 */
export function normalizeRichTextEntities(html: string): string {
  if (!html) return html;
  return html.replace(NESTED_ENTITY_PATTERN, "&$1");
}

/**
 * Keep saved table markup semantic while adding a dedicated responsive scroll
 * frame. The frame prevents wide pasted tables from widening the page and lets
 * the table itself retain native column sizing.
 */
export function wrapRichTextTables(html: string): string {
  const normalized = normalizeRichTextEntities(html);
  if (!normalized || !/<table\b/i.test(normalized)) return normalized;
  return normalized.replace(
    TABLE_PATTERN,
    (table) =>
      `<div class="rich-table-scroll" role="region" aria-label="Scrollable table" tabindex="0">${table}</div>`,
  );
}
