import { cache } from "react";

export type Observation = { year: string; value: number };
export type MarketSeries = {
  code: string; title: string; unit: string; points: Observation[];
  latest: Observation; source_url: string; api_url: string;
};
export type MarketSummary = { month: string; published_at: string; unemployment: Observation };
export type MarketReport = {
  schema_version: number; month: string; published_at: string;
  national_data_changed: boolean | null;
  national: { series: Record<string, MarketSeries>; provider: string; source_updated: string[]; license_url: string };
  site_supplement: { month: string; total: number; government: number; private: number; unspecified: number; scope: string; source_url: string };
};

const API = (process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const monthLabel = (month: string) => new Date(`${month}-01T12:00:00Z`).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });

export const fetchMarketReports = cache(async (): Promise<MarketSummary[]> => {
  const res = await fetch(`${API}/api/market-reports`, { next: { revalidate: 300 }, signal: AbortSignal.timeout(15000) });
  // Allows the frontend build to precede the backend rollout of the new route.
  if (res.status === 404) return [];
  if (!res.ok) throw new Error("Monthly reports are temporarily unavailable");
  return (await res.json()).reports;
});

export const fetchMarketReport = cache(async (month: string): Promise<MarketReport | null> => {
  if (!/^[0-9]{4}-(0[1-9]|1[0-2])$/.test(month)) return null;
  const res = await fetch(`${API}/api/market-reports/${month}`, { next: { revalidate: 300 }, signal: AbortSignal.timeout(15000) });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Monthly report is temporarily unavailable");
  return res.json();
});

/** Compare populations in the same reference year, never mismatched latests. */
export function commonObservations(series: MarketSeries[]) {
  const year = series[0]?.points.map(p => p.year).reverse().find(y => series.every(s => s.points.some(p => p.year === y)));
  return year ? { year, points: series.map(s => s.points.find(p => p.year === year)!) } : null;
}
