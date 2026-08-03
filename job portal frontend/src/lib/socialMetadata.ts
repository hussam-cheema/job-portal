const IMAGE_SOURCE_PATTERN =
  /<img\b[^>]*?\bsrc\s*=\s*(?:"([^"]+)"|'([^']+)'|([^\s>]+))/i;

function decodeHtmlAttribute(value: string): string {
  return value
    .replace(/&amp;/gi, "&")
    .replace(/&#38;/g, "&")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/g, "'");
}

function usableImageUrl(value: string | null | undefined): string | null {
  const candidate = decodeHtmlAttribute((value || "").trim());
  if (!candidate) return null;
  if (candidate.startsWith("//")) return `https:${candidate}`;
  if (candidate.startsWith("/")) return candidate;
  try {
    const url = new URL(candidate);
    return /^https?:$/i.test(url.protocol) ? url.toString() : null;
  } catch {
    return null;
  }
}

export function firstRichTextImage(html: string | null | undefined): string | null {
  const match = (html || "").match(IMAGE_SOURCE_PATTERN);
  return usableImageUrl(match?.[1] || match?.[2] || match?.[3]);
}

export function selectSocialImage(
  ...candidates: Array<string | null | undefined>
): string {
  for (const candidate of candidates) {
    const image = usableImageUrl(candidate);
    if (image) return image;
  }
  return "/pakistan-jobs-market-logo.png";
}

export function compactSocialDescription(value: string): string {
  return value.replace(/\s+/g, " ").trim().slice(0, 200);
}
