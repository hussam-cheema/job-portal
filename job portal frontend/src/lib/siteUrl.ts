export function canonicalSiteUrl(
  raw = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000",
): string {
  const fallback = raw.replace(/\/$/, "");
  try {
    const url = new URL(raw);
    if (["pakistanjobsmarket.com", "www.pakistanjobsmarket.com"].includes(url.hostname)) {
      url.protocol = "https:";
      url.hostname = "pakistanjobsmarket.com";
      url.port = "";
      url.pathname = "";
      url.search = "";
      url.hash = "";
      return url.toString().replace(/\/$/, "");
    }
  } catch {
    return fallback;
  }
  return fallback;
}

export function canonicalizePublicUrl(value: string, site = canonicalSiteUrl()): string {
  try {
    const url = new URL(value, site);
    if (["pakistanjobsmarket.com", "www.pakistanjobsmarket.com"].includes(url.hostname)) {
      url.protocol = "https:";
      url.hostname = "pakistanjobsmarket.com";
      url.port = "";
    }
    return url.toString();
  } catch {
    return value;
  }
}
