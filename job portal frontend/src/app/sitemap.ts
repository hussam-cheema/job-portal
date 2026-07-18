import type { MetadataRoute } from "next";
import { toSeoSlug } from "@/lib/slug";

const SITE = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, "");
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
    { url: `${SITE}/blog`, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE}/resume-builder`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE}/cover-letter`, changeFrequency: "monthly", priority: 0.6 },
  ];

  try {
    const res = await fetch(`${API}/api/sitemap-data`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      for (const item of data.urls || []) {
        if (entries.some((entry) => entry.url === item.loc)) continue;
        entries.push({
          url: item.loc,
          lastModified: item.lastmod || undefined,
          changeFrequency: item.changefreq || "weekly",
          priority: Number(item.priority ?? 0.5),
        });
      }
    }
  } catch {
    /* keep static entries if the API is unavailable */
  }

  try {
    const res = await fetch(`${API}/api/filters`, { cache: "no-store" });
    if (res.ok) {
      const filters = await res.json();
      for (const tag of filters.tags || []) {
        entries.push({
          url: `${SITE}/tags/${toSeoSlug(tag)}`,
          changeFrequency: "weekly",
          priority: 0.5,
        });
      }
      for (const category of filters.categories || []) {
        entries.push({
          url: `${SITE}/categories/${toSeoSlug(category)}`,
          changeFrequency: "weekly",
          priority: 0.6,
        });
      }
    }
  } catch {
    /* ignore */
  }

  return entries;
}
