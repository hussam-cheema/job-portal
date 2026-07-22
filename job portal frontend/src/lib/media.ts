const R2_INLINE_IMAGE_PATH =
  /^\/?([^?#]*\/(?:images|branding)\/[^/?#]+\.(?:png|jpe?g|gif|webp|bmp))$/i;

function publicApiBase() {
  return (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
}

/**
 * Route stored R2 images through the backend media endpoint.
 *
 * Existing descriptions keep their durable R2 URLs in the database. Rewriting
 * only at render time means old posts recover automatically and the storage
 * provider can still be changed without rewriting saved HTML.
 */
export function rewriteJobDescriptionImages(html: string): string {
  if (!html || !/<img\b/i.test(html)) return html;

  return html.replace(
    /(<img\b[^>]*?\bsrc\s*=\s*)(["'])([^"']+)(\2)/gi,
    (full, prefix: string, quote: string, source: string) => {
      try {
        const url = new URL(source);
        if (!/^https?:$/i.test(url.protocol)) return full;
        const match = url.pathname.match(R2_INLINE_IMAGE_PATH);
        const key = match?.[1]?.replace(/^\//, "");
        if (!key) return full;
        const proxied = `${publicApiBase()}/api/media/r2/${key
          .split("/")
          .map(encodeURIComponent)
          .join("/")}`;
        return `${prefix}${quote}${proxied}${quote}`;
      } catch {
        return full;
      }
    }
  );
}

function imageSources(html: string): string[] {
  if (!html || !/<img\b/i.test(html)) return [];
  return Array.from(
    html.matchAll(/<img\b[^>]*?\bsrc\s*=\s*["']([^"']+)["']/gi),
    (match) => match[1],
  );
}

/**
 * Keep the editor's display-only media proxy out of persisted rich text.
 *
 * Quill must load an existing R2 image through the backend proxy (the public
 * R2 hostname may be unavailable to the browser), while the database should
 * continue storing the durable R2 URL. This maps any proxy sources emitted by
 * Quill back to the corresponding source in the value received from the API.
 */
export function restoreStoredJobDescriptionImages(
  editorHtml: string,
  storedHtml: string,
): string {
  if (!editorHtml || !/<img\b/i.test(editorHtml) || !storedHtml) return editorHtml;

  const storedSources = imageSources(storedHtml);
  const displaySources = imageSources(rewriteJobDescriptionImages(storedHtml));
  const replacements = new Map<string, string>();
  displaySources.forEach((source, index) => {
    const storedSource = storedSources[index];
    if (storedSource && source !== storedSource) replacements.set(source, storedSource);
  });
  if (!replacements.size) return editorHtml;

  return editorHtml.replace(
    /(<img\b[^>]*?\bsrc\s*=\s*)(["'])([^"']+)(\2)/gi,
    (full, prefix: string, quote: string, source: string) => {
      const replacement = replacements.get(source);
      return replacement ? `${prefix}${quote}${replacement}${quote}` : full;
    },
  );
}
