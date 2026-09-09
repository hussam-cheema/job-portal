"use client";

import { useState } from "react";
import Link from "next/link";
import { monthLabel, type ListingCounts, type SiteStatistics } from "@/lib/marketReports";
import styles from "./MarketDashboard.module.css";
import { EmploymentBars } from "./EmploymentBreakdowns";

function Counts({ counts }: { counts: ListingCounts }) {
  return <p><strong>{counts.total.toLocaleString("en-GB")}</strong> listings · {counts.government.toLocaleString("en-GB")} government · {counts.private.toLocaleString("en-GB")} private · {counts.unspecified.toLocaleString("en-GB")} unspecified</p>;
}

export function SiteListingStatistics({ data }: { data: SiteStatistics | null }) {
  const [month, setMonth] = useState(data?.current_month || "");
  const [graphScope, setGraphScope] = useState("overall");
  const selected = data?.months.find(item => item.month === month) || data?.months.find(item => item.month === data.current_month);
  const charts = graphScope === "overall" ? data?.breakdowns?.overall : data?.breakdowns?.months[selected?.month || ""];
  return <section className={styles.supplement} aria-label="Website-only supplementary statistics">
    <div><p className={styles.eyebrow}>Website listings · not national statistics</p><h2>From Pakistan Jobs Market’s own listings</h2>
      <p>Current website inventory, including open and expired advertisements—not vacancies or national hiring totals. Monthly counts use each advertisement’s publication date, not the date it was added here.</p>
      {data && <p>Updated {new Date(data.collected_at).toLocaleString("en-GB", { timeZone: "Asia/Karachi" })} PKT. Counts are cached briefly; reload to check for updates. These current counts are separate from the archived national report.</p>}
      <Link href="/">Source: website job listings →</Link>
    </div>
    {data ? <div className={styles.listingTotals}>
      <div><h3>Overall · all publication dates</h3><Counts counts={data.overall}/></div>
      <div><label htmlFor="website-listing-month">By publication month</label><select id="website-listing-month" value={selected?.month || ""} onChange={event => setMonth(event.target.value)}>{data.months.map(item => <option key={item.month} value={item.month}>{monthLabel(item.month)}{item.month === data.current_month ? " · current month" : ""}</option>)}</select>{selected && <Counts counts={selected}/>}</div>
      {data.undated.total > 0 && <p>{data.undated.total} undated listings are included in overall totals only.</p>}
    </div> : <p>Current website listing statistics are temporarily unavailable.</p>}
    {data?.breakdowns && <details className={styles.websiteBreakdowns}>
      <summary>Explore website jobs by occupation and province</summary>
      <div className={styles.chartToolbar}><label htmlFor="website-graph-period">Graph period<select id="website-graph-period" value={graphScope} onChange={event => setGraphScope(event.target.value)}><option value="overall">Overall · all dates</option><option value="month">Selected month · {selected ? monthLabel(selected.month) : "Unavailable"}</option></select></label></div>
      <div className={styles.twoColumns}>
        <section className={styles.panel}><h3>Website jobs by occupation</h3><p>Advertisement counts grouped from explicit occupational tags. Unclassified means no recognized occupation tag; government/private and employer names are not occupations. A multi-role advertisement is counted once.</p>
          <EmploymentBars items={charts?.occupations || []} unit="listings" label="Website jobs by occupation"/>
        </section>
        <section className={styles.panel}><h3>Website jobs by province / territory</h3><p>One count per advertisement per applicable province. Multi-province listings may appear in several bars, so do not sum them as unique jobs. Nationwide listings are separate, not copied into every province.</p>
          <EmploymentBars items={charts?.provinces || []} unit="listings" label="Website jobs by province"/>
        </section>
      </div>
      <p>Source: current website job records. Publication month controls the monthly view. Bars are scaled to the largest category; these are not national employment statistics or vacancy counts.</p>
    </details>}
  </section>;
}
