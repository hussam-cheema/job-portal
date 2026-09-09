import type { BreakdownItem, NationalBreakdowns } from "@/lib/marketReports";
import styles from "./MarketDashboard.module.css";

export function EmploymentBars({ items, unit, label }: { items: BreakdownItem[]; unit: "percent" | "million" | "listings"; label: string }) {
  const max = Math.max(1, ...items.map(item => item.value));
  return items.length ? <ul className={styles.breakdownBars} aria-label={label}>{items.map((item, index) => <li key={item.name}>
    <div><span>{item.name}</span><strong>{unit === "listings" ? item.value.toLocaleString("en-GB") : item.value.toFixed(1)}{unit === "percent" ? "%" : unit === "million" ? "m" : ""}</strong></div>
    <div className={styles.track} aria-hidden="true"><span style={{ width: `${item.value / max * 100}%`, background: ["#7762e8", "#20a993", "#3184d7", "#d68a2d"][index % 4] }}/></div>
  </li>)}</ul> : <p>No listings for this period.</p>;
}

export function NationalEmploymentBreakdowns({ data, archived }: { data: NationalBreakdowns; archived: boolean }) {
  return <section id="national-breakdowns" aria-label="Official Pakistan occupation and province statistics">
    <div className={styles.twoColumns}>
      <section className={styles.panel}><p className={styles.eyebrow}>Official Pakistan employment · PBS</p><h2>Employment by occupation</h2>
        <p>{data.period} · share of employed persons (%) · PSCO-2015 occupation groups.</p>
        <EmploymentBars items={data.occupations.items} unit="percent" label="Pakistan employment by occupation"/>
        <a className={styles.sourceLink} href={data.occupations.source_url}>PBS LFS {data.period} · Table {data.occupations.table}, page {data.occupations.page} ↗</a>
      </section>
      <section className={styles.panel}><p className={styles.eyebrow}>Official Pakistan employment · PBS</p><h2>Employment by province</h2>
        <p>{data.period} · employed persons in millions.</p>
        <EmploymentBars items={data.provinces.items} unit="million" label="Pakistan employment by province"/>
        <p><strong>Pakistan total: {data.provinces.pakistan_total.toFixed(1)} million employed people.</strong></p>
        <a className={styles.sourceLink} href={data.provinces.source_url}>PBS LFS {data.period} · Table {data.provinces.table}, page {data.provinces.page} ↗</a>
        <p className={styles.caption}>{data.definition} These survey figures use a different population and methodology from the World Bank / ILO trend charts.</p>
        <p className={styles.caption}>{data.notes}</p>
        <p className={styles.caption}>{archived ? "Survey snapshot preserved in this edition." : "Additional reviewed survey detail alongside the monthly edition."} Verified {data.verified_at}. Bars are scaled to each chart’s largest value.</p>
      </section>
    </div>
  </section>;
}
