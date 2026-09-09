import Link from "next/link";
import type { CSSProperties } from "react";
import { MarketTrend } from "@/components/MarketCharts";
import { SiteListingStatistics } from "@/components/SiteListingStatistics";
import { NationalEmploymentBreakdowns } from "@/components/EmploymentBreakdowns";
import type { SiteStatistics, NationalBreakdowns } from "@/lib/marketReports";
import { commonObservations, monthLabel, type MarketReport, type MarketSeries, type MarketSummary } from "@/lib/marketReports";
import { canonicalSiteUrl } from "@/lib/siteUrl";
import styles from "./MarketDashboard.module.css";

const pct = (n: number) => `${n.toFixed(1)}%`;
const palette = ["#7762e8", "#20a993", "#e8a045"];

function Comparison({ title, items, names, note }: { title: string; items: MarketSeries[]; names: string[]; note: string }) {
  const common = commonObservations(items);
  return <section className={styles.panel}><p className={styles.eyebrow}>People & participation</p><h2>{title}</h2><p>{note}</p>
    {common ? <><span className={styles.period}>{common.year} · ILO modelled estimates</span><div className={styles.bars}>{common.points.map((point, i) => <div key={names[i]} className={styles.barRow}><div><span>{names[i]}</span><strong>{pct(point.value)}</strong></div><div className={styles.track}><span style={{ width: `${point.value}%`, background: palette[i] }}/></div></div>)}</div></> : <p>No common reporting year is available for this comparison.</p>}
    <div className={styles.sourcesInline}>{items.map((s, i) => <a key={s.code} href={s.source_url}>{names[i]} source ↗</a>)}</div>
  </section>;
}

export function MarketDashboard({ report, reports, archive = false, siteStatistics = null, nationalBreakdowns = null }: { report: MarketReport | null; reports: MarketSummary[]; archive?: boolean; siteStatistics?: SiteStatistics | null; nationalBreakdowns?: NationalBreakdowns | null }) {
  const series = report?.national.series;
  const breakdowns = archive ? report?.national.breakdowns : nationalBreakdowns || report?.national.breakdowns;
  const sectorKeys = ["agriculture", "industry", "services"];
  const sector = series ? commonObservations(sectorKeys.map(k => series[k])) : null;
  const gender = series ? commonObservations([series.female_participation, series.male_participation]) : null;
  const youth = series ? commonObservations([series.youth_unemployment, series.unemployment]) : null;
  const site = canonicalSiteUrl();
  const title = archive && report ? `Pakistan job market report — ${monthLabel(report.month)}` : "Pakistan job market, in perspective.";
  const schema = report ? {
    "@context": "https://schema.org", "@type": "Report", headline: `Pakistan Job Market Report — ${monthLabel(report.month)}`,
    description: "A monthly edition of national labour-market indicators for Pakistan, with annual World Bank / ILO observations and transparent source dates.",
    datePublished: report.published_at, dateModified: report.published_at,
    mainEntityOfPage: `${site}/dashboard/${report.month}`, inLanguage: "en", spatialCoverage: { "@type": "Country", name: "Pakistan" },
    author: { "@type": "Organization", name: "Pakistan Jobs Market", url: site },
    publisher: { "@type": "Organization", name: "Pakistan Jobs Market", url: site },
    citation: [...Object.values(report.national.series).map(s => s.source_url), ...(breakdowns ? [breakdowns.source_url] : [])],
  } : null;
  return <div className={`site-wrap ${styles.dashboard}`}>
    {schema && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }}/>}
    <header className={styles.hero}>
      <div><p className={styles.heroKicker}>THE NATIONAL PICTURE · MONTHLY BRIEFING</p><h1>{title}</h1><p>Understand work, opportunity and participation across Pakistan. Official statistics, useful comparisons, and a clearer view of the labour market.</p>
        <div className={styles.heroLinks}><a href="#national-overview">Explore the report ↓</a><a href="#report-archive">Browse editions</a></div>
      </div>
<aside className={styles.edition}><span className={styles.editionDot}/> {report ? "PUBLISHED EDITION" : "MONTHLY EDITIONS"}<strong>{report ? monthLabel(report.month) : "Coming soon"}</strong><p>National coverage<br/>World Bank / ILO · PBS survey data</p><span>New edition every month · Pakistan time</span></aside>
    </header>
    <nav aria-label="Report sections" className={styles.sectionNav}><a href="#national-overview">Overview</a><a href="#market-trends">Trends</a><a href="#employment-sectors">Sectors</a>{breakdowns && <a href="#national-breakdowns">Occupations & provinces</a>}<a href="#workforce">Workforce</a><a href="#methodology">Methodology</a><a href="#report-sources">Sources</a></nav>
    {!report || !series ? <section className={styles.panel}><h2>The first national report is being prepared</h2><p>Official data must pass validation before an edition can be published. No estimated or placeholder numbers are shown here. Please check back shortly.</p></section> : <>
      <div className={styles.timingNote}><strong>A monthly edition, not a monthly survey.</strong> The figures below are annual national estimates; each shows its observation year. Retrieved on {new Date(report.published_at).toLocaleDateString("en-GB", { timeZone: "Asia/Karachi" })}. {report.national_data_changed === false ? "The official series are unchanged since the previous edition." : "Official series can be revised between editions."} {archive && <Link href="/dashboard">See the latest edition →</Link>}</div>
      <section id="national-overview" className={styles.stats} aria-label="National key indicators">
        {[["unemployment", "Unemployment", "Of the labour force, ages 15+"], ["youth_unemployment", "Youth unemployment", "Of the youth labour force, ages 15–24"], ["participation", "Labour force participation", "Of the population ages 15+"], ["employment_ratio", "Employment-to-population", "Of the population ages 15+"]].map(([key, label, note], i) => <article key={key} className={styles.stat} style={{ "--metric-color": palette[i % 3] } as CSSProperties}><span className={styles.statLabel}>{label}</span><strong>{pct(series[key].latest.value)}</strong><p>{note}</p><a href={series[key].source_url}>{series[key].latest.year} · ILO estimate ↗</a></article>)}
      </section>
      <section id="market-trends" className={styles.panel}><div className={styles.sectionHeading}><div><p className={styles.eyebrow}>The longer view</p><h2>How Pakistan’s labour market is changing</h2></div><span className={styles.pill}>Annual series</span></div><MarketTrend series={series}/></section>
      {breakdowns && <NationalEmploymentBreakdowns data={breakdowns} archived={archive}/>}
      <div className={styles.twoColumns}>
        <section id="employment-sectors" className={styles.panel}><p className={styles.eyebrow}>Where people work</p><h2>Employment by sector</h2><p>Share of total employment—not advertised vacancies or GDP.</p>
          {sector ? <><span className={styles.period}>{sector.year} · ILO modelled estimates</span><div className={styles.sectorBody}><div className={styles.donut} role="img" aria-label={sectorKeys.map((k, i) => `${k}: ${pct(sector.points[i].value)}`).join(", ")} style={{ background: `conic-gradient(${palette[0]} 0% ${sector.points[0].value}%, ${palette[1]} ${sector.points[0].value}% ${sector.points[0].value + sector.points[1].value}%, ${palette[2]} ${sector.points[0].value + sector.points[1].value}% 100%)` }}><span>Pakistan<strong>{sector.year}</strong></span></div><ul className={styles.legend}>{sectorKeys.map((key, i) => <li key={key}><i style={{ background: palette[i] }}/><a href={series[key].source_url}>{key}</a><strong>{pct(sector.points[i].value)}</strong></li>)}</ul></div></> : <p>No shared year is available for the three sectors.</p>}
          <p className={styles.caption}>Rounded shares may not add to exactly 100%. Select a sector label to view its official source.</p>
        </section>
        <section className={`${styles.panel} ${styles.insightPanel}`}><p className={styles.eyebrow}>Read between the numbers</p><h2>Three takeaways</h2><ol className={styles.insights}>
          <li><strong>Youth and the wider labour force</strong><p>{youth ? `In ${youth.year}, youth unemployment was ${pct(youth.points[0].value)}, compared with ${pct(youth.points[1].value)} overall. These are different age groups, not counts of job seekers.` : "Reporting years differ, so a direct comparison is not shown."}</p><a href={series.youth_unemployment.source_url}>Youth indicator ↗</a></li>
          <li><strong>Participation matters too</strong><p>{gender ? `The male–female participation difference was ${(gender.points[1].value - gender.points[0].value).toFixed(1)} percentage points in ${gender.year}. People outside the labour force are not counted as unemployed.` : "Participation and unemployment measure different populations."}</p><a href={series.participation.source_url}>Participation definition ↗</a></li>
          <li><strong>Employment is broader than vacancies</strong><p>Sector shares include existing workers and self-employment. A large sector is not, by itself, evidence of a recruitment surge.</p><Link href="/jobs-by-categories">Explore advertised opportunities →</Link></li>
        </ol></section>
      </div>
      <div id="workforce" className={styles.twoColumns}><Comparison title="Who participates in the workforce?" names={["Women", "Men"]} items={[series.female_participation, series.male_participation]} note="Labour force participation as a share of each population ages 15+."/><Comparison title="Unemployment by gender" names={["Women", "Men"]} items={[series.female_unemployment, series.male_unemployment]} note="Unemployed people as a share of the respective labour force, ages 15+."/></div>
      <section className={styles.panel}><p className={styles.eyebrow}>Beyond the headline rate</p><h2>What kinds of work support livelihoods?</h2><p>Employment status helps put job-market conditions in context. These measures overlap; they must not be added together.</p><div className={styles.workTypes}>{[["wage_employment", "Wage & salaried work", "Employees receiving wages or a salary."], ["self_employment", "Self-employment", "Includes employers, own-account and contributing family workers."], ["vulnerable_employment", "Vulnerable employment", "Own-account and contributing family workers; not a direct poverty measure."]].map(([key, label, note]) => <article key={key}><strong>{pct(series[key].latest.value)}</strong><h3>{label}</h3><p>{note}</p><a href={series[key].source_url}>{series[key].latest.year} · % of employment ↗</a></article>)}</div></section>
      <section id="methodology" className={styles.panel}><p className={styles.eyebrow}>Transparent by design</p><h2>How to read this Pakistan employment report</h2><div className={styles.methodGrid}>
        <div><h3>National estimates, consistent definitions</h3><p>The main dashboard uses Pakistan observations from the World Bank’s World Development Indicators, sourced from ILO modelled estimates. Labour force participation includes employed people and unemployed people seeking and available for work. Unemployment is not the share of all residents without a job.</p></div>
        <div><h3>Publication month versus data year</h3><p>A new edition retrieves the latest available official series each month. Annual observations may stay unchanged across several editions. The reporting year is visible beside every metric; retrieval dates describe our snapshot, not when workers were surveyed.</p></div>
        <div><h3>Comparisons without mixing populations</h3><p>Gender and sector charts use a shared observation year. Youth refers to ages 15–24; the other participation and employment ratios cover ages 15+. Percentage-point gaps are calculated from the cited series. Missing data is never treated as zero.</p></div>
        <div><h3>Survey figures can differ</h3><p>Pakistan Bureau of Statistics survey results may use different age coverage, definitions and reference periods from the internationally comparable ILO estimates here. Consult the <a href="https://www.pbs.gov.pk/labour-force-statistics/">official PBS Labour Force Survey</a> for survey-specific tables. Do not splice the two series into one trend.</p></div>
      </div><p className={styles.caption}>This is an independent presentation of official statistics, not an official government publication, real-time vacancy count, hiring forecast, or guarantee of employment.</p></section>
      <section className={styles.actionStrip}><div><p className={styles.eyebrow}>From insight to action</p><h2>Make your next application count.</h2><p>Use the national context alongside the requirements of a specific role.</p></div><div><Link href="/tools/resume-builder">Build a resume →</Link><Link href="/tools/pakistan-tax-calculator">Estimate take-home pay →</Link><Link href="/blog">Read career guides →</Link></div></section>
      <section id="report-sources" className={styles.panel}><p className={styles.eyebrow}>Open evidence</p><h2>Sources & data provenance</h2><p>The trend and rate indicators come from the official World Bank API for Pakistan (PAK), WDI source 2, with ILO attribution. Occupation and province charts cite the separate PBS Labour Force Survey tables beside each graph. Provider dataset update: {report.national.source_updated.join(", ")}. Retrieved: <time dateTime={report.published_at}>{new Date(report.published_at).toLocaleString("en-GB", { timeZone: "Asia/Karachi" })} PKT</time>. <a href={report.national.license_url}>Data licence: CC BY 4.0</a>.</p>
        <details className={styles.dataTable}><summary>View all 14 official indicators and downloadable source data</summary><ul className={styles.sourceList}>{Object.values(series).map(s => <li key={s.code}><a href={s.source_url}>{s.title} ↗</a><span>{s.latest.year} · {s.code}</span><a href={s.api_url}>Source JSON</a></li>)}</ul></details>
      </section>
    </>}
    <section id="report-archive" className={styles.panel}><p className={styles.eyebrow}>The report library</p><h2>Browse monthly editions</h2><p>Each edition has a permanent link and preserves the official data retrieved at publication. The archive begins with our first published edition; older annual observations are available in the trend charts, not presented as invented past monthly reports.</p><nav className={styles.archiveGrid} aria-label="Monthly report archive">{reports.map(r => <Link href={`/dashboard/${r.month}`} key={r.month} aria-current={report?.month === r.month ? "page" : undefined}><span>MONTHLY REPORT</span><strong>{monthLabel(r.month)}</strong><span>National job market briefing ↗</span></Link>)}</nav></section>
    <SiteListingStatistics data={siteStatistics}/>
  </div>;
}
