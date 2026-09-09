import { selectSocialImage } from "@/lib/socialMetadata";
import type { Metadata } from "next";
import { MarketDashboard } from "@/components/MarketDashboard";
import { fetchMarketReport, fetchMarketReports, fetchSiteStatistics, fetchNationalBreakdowns } from "@/lib/marketReports";

export const revalidate = 300;
export const metadata: Metadata = {
  title: "Pakistan Job Market Dashboard | National Employment Statistics",
  description: "Explore Pakistan employment by occupation and province, unemployment, gender gaps and sectors with official PBS and World Bank / ILO data and monthly report archives.",
  alternates: { canonical: "/dashboard" },
  keywords: ["Pakistan job market statistics", "Pakistan unemployment rate", "Pakistan employment report", "labour force participation Pakistan"],
  openGraph: { title: "Pakistan Job Market Dashboard", url: "/dashboard", type: "website", description: "National labour-market statistics, visual trends and monthly editions with official sources.", images: [{ url: selectSocialImage() }] },
};

export default async function DashboardPage() {
  const reports = await fetchMarketReports();
  const report = reports[0] ? await fetchMarketReport(reports[0].month) : null;
  const [siteStatistics, nationalBreakdowns] = await Promise.all([fetchSiteStatistics(), fetchNationalBreakdowns()]);
  return <MarketDashboard report={report} reports={reports} siteStatistics={siteStatistics} nationalBreakdowns={nationalBreakdowns}/>;
}
