import type { MetadataRoute } from "next";
import { toSeoSlug } from "@/lib/slug";

const SITE = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, "");
const API = (
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"
).replace(/\/$/, "");

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const entries: MetadataRoute.Sitemap = [
    { url: `${SITE}/`, changeFrequency: "daily", priority: 1 },
    { url: `${SITE}/about`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE}/contact`, changeFrequency: "monthly", priority: 0.5 },
    { url: `${SITE}/privacy`, changeFrequency: "yearly", priority: 0.3 },
  ];

  try {
    const res = await fetch(`${API}/api/jobs?page_size=100`, {
      next: { revalidate: 60 },
    });
    if (res.ok) {
      const data = await res.json();
      for (const job of data.items || []) {
        entries.push({
          url: `${SITE}/jobs/${job.slug || job.id}`,
          lastModified: job.published_date || job.created_at || undefined,
          changeFrequency: "weekly",
          priority: 0.8,
        });
      }
    }
  } catch {
    /* keep static entries */
  }

  try {
    const res = await fetch(`${API}/api/pages`, { next: { revalidate: 60 } });
    if (res.ok) {
      const pages = await res.json();
      for (const p of pages || []) {
        if (["about", "contact", "privacy"].includes(p.slug)) continue;
        entries.push({
          url: `${SITE}/p/${p.slug}`,
          lastModified: p.updated_at || undefined,
          changeFrequency: "monthly",
          priority: 0.5,
        });
      }
    }
  } catch {
    /* ignore */
  }

  try {
    const res = await fetch(`${API}/api/filters`, { next: { revalidate: 60 } });
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
