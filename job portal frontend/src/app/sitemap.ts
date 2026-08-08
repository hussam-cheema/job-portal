import type { MetadataRoute } from "next";
import { toSeoSlug } from "@/lib/slug";
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
    { url: `${SITE}/resume-builder`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE}/cover-letter`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE}/browse`, changeFrequency: "daily", priority: 0.8 },
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

  try {
    const res = await fetch(`${API}/api/filters`, { cache: "no-store" });
    if (res.ok) {
      const filters = await res.json();
      for (const tag of filters.tags || []) {
        if (!entries.some((entry) => entry.url === `${SITE}/tags/${toSeoSlug(tag)}`)) entries.push({
          url: `${SITE}/tags/${toSeoSlug(tag)}`,
          changeFrequency: "weekly",
          priority: 0.5,
        });
      }
      for (const category of filters.categories || []) {
        if (!entries.some((entry) => entry.url === `${SITE}/categories/${toSeoSlug(category)}`)) entries.push({
          url: `${SITE}/categories/${toSeoSlug(category)}`,
          changeFrequency: "weekly",
          priority: 0.6,
        });
      }
      for (const company of filters.companies || []) {
        if (!entries.some((entry) => entry.url === `${SITE}/companies/${toSeoSlug(company)}`)) entries.push({
          url: `${SITE}/companies/${toSeoSlug(company)}`,
          changeFrequency: "weekly",
          priority: 0.6,
        });
      }
      for (const location of [...(filters.provinces || []), ...(filters.cities || [])]) {
        if (!entries.some((entry) => entry.url === `${SITE}/locations/${toSeoSlug(location)}`)) entries.push({
          url: `${SITE}/locations/${toSeoSlug(location)}`,
          changeFrequency: "weekly",
          priority: 0.5,
        });
      }
      for (const qualification of filters.qualifications || []) {
        if (!entries.some((entry) => entry.url === `${SITE}/qualifications/${toSeoSlug(qualification)}`)) entries.push({
          url: `${SITE}/qualifications/${toSeoSlug(qualification)}`,
          changeFrequency: "weekly",
          priority: 0.5,
        });
      }
    }
  } catch {
    /* ignore */
  }

  return Array.from(new Map(entries.map((entry) => [entry.url, entry])).values());
}
