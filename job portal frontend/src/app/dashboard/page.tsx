import type { Metadata } from "next";
import { MarketDashboard } from "@/components/MarketDashboard";
import { fetchMarketReport, fetchMarketReports, fetchSiteStatistics } from "@/lib/marketReports";

export const revalidate = 300;
export const metadata: Metadata = {
  title: "Pakistan Job Market Dashboard | National Employment Statistics",
  description: "Explore Pakistan’s unemployment, youth employment, gender gaps and employment sectors with official World Bank / ILO data, annual trends and monthly report archives.",
  alternates: { canonical: "/dashboard" },
  keywords: ["Pakistan job market statistics", "Pakistan unemployment rate", "Pakistan employment report", "labour force participation Pakistan"],
  openGraph: { title: "Pakistan Job Market Dashboard", url: "/dashboard", type: "website", description: "National labour-market statistics, visual trends and monthly editions with official sources." },
};

export default async function DashboardPage() {
  const reports = await fetchMarketReports();
  const report = reports[0] ? await fetchMarketReport(reports[0].month) : null;
  return <MarketDashboard report={report} reports={reports} siteStatistics={await fetchSiteStatistics()}/>;
}
