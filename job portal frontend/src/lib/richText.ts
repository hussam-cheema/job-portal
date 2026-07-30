const TABLE_PATTERN = /<table\b[^>]*>[\s\S]*?<\/table>/gi;

/**
 * Keep saved table markup semantic while adding a dedicated responsive scroll
 * frame. The frame prevents wide pasted tables from widening the page and lets
 * the table itself retain native column sizing.
 */
export function wrapRichTextTables(html: string): string {
  if (!html || !/<table\b/i.test(html)) return html;
  return html.replace(
    TABLE_PATTERN,
    (table) =>
      `<div class="rich-table-scroll" role="region" aria-label="Scrollable table" tabindex="0">${table}</div>`,
  );
}
