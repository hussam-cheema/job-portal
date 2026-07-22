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
