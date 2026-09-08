import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { MarketDashboard } from "@/components/MarketDashboard";
import { fetchMarketReport, fetchMarketReports, fetchSiteStatistics, monthLabel } from "@/lib/marketReports";

export const revalidate = 300;
type Props = { params: Promise<{ month: string }> };

export async function generateStaticParams() {
  return (await fetchMarketReports()).map(r => ({ month: r.month }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { month } = await params;
  const report = await fetchMarketReport(month);
  if (!report) return { title: "Report not found", robots: { index: false, follow: true } };
  const title = `Pakistan Job Market Report — ${monthLabel(month)}`;
  const unemployment = report.national.series.unemployment.latest;
  const description = `${monthLabel(month)} edition: Pakistan unemployment (${unemployment.year} ILO estimate: ${unemployment.value.toFixed(1)}%), workforce participation, youth and sector trends. Official sources and methodology included.`;
  return { title, description, alternates: { canonical: `/dashboard/${month}` }, openGraph: { title, description, url: `/dashboard/${month}`, type: "article", publishedTime: report.published_at, modifiedTime: report.published_at } };
}

export default async function MonthlyReportPage({ params }: Props) {
  const { month } = await params;
  const report = await fetchMarketReport(month);
  if (!report) notFound();
  return <MarketDashboard report={report} reports={await fetchMarketReports()} siteStatistics={await fetchSiteStatistics()} archive/>;
}
