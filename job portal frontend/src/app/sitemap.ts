import type { MetadataRoute } from "next";
import { canonicalizePublicUrl, canonicalSiteUrl } from "@/lib/siteUrl";

const SITE = canonicalSiteUrl();
const API = (
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"
).replace(/\/$/, "");

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const entries: MetadataRoute.Sitemap = [
    { url: `${SITE}/`, changeFrequency: "daily", priority: 1 },
    { url: `${SITE}/about`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE}/contact`, changeFrequency: "monthly", priority: 0.5 },
    { url: `${SITE}/privacy`, changeFrequency: "yearly", priority: 0.3 },
    { url: `${SITE}/disclaimer`, changeFrequency: "yearly", priority: 0.3 },
    { url: `${SITE}/blog`, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE}/dashboard`, changeFrequency: "monthly", priority: 0.9 },
    { url: `${SITE}/tools/resume-builder`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE}/tools/cover-letter`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE}/tools`, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE}/browse`, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE}/jobs-by-cities`, changeFrequency: "weekly", priority: 0.7 },
    { url: `${SITE}/jobs-by-provinces`, changeFrequency: "weekly", priority: 0.7 },
    { url: `${SITE}/jobs-by-categories`, changeFrequency: "weekly", priority: 0.7 },
    { url: `${SITE}/jobs-by-organizations`, changeFrequency: "weekly", priority: 0.7 },
    { url: `${SITE}/jobs-by-newspapers`, changeFrequency: "weekly", priority: 0.7 },
  ];

  try {
    const res = await fetch(`${API}/api/sitemap-data`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      for (const item of data.urls || []) {
        const url = canonicalizePublicUrl(item.loc, SITE);
        if (entries.some((entry) => entry.url === url)) continue;
        entries.push({
          url,
          lastModified: item.lastmod || undefined,
          changeFrequency: item.changefreq || "weekly",
          priority: Number(item.priority ?? 0.5),
        });
      }
    }
  } catch {
    /* keep static entries if the API is unavailable */
  }

  return Array.from(new Map(entries.map((entry) => [entry.url, entry])).values());
}
