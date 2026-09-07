"use client";

import { useState } from "react";
import type { MarketSeries } from "@/lib/marketReports";
import styles from "@/components/MarketDashboard.module.css";

export function MarketTrend({ series }: { series: Record<string, MarketSeries> }) {
  const [selected, setSelected] = useState("unemployment");
  const [active, setActive] = useState<number | null>(null);
  const current = series[selected];
  const points = current.points.slice(-12);
  const point = points[active ?? points.length - 1];
  const max = Math.max(1, Math.ceil(Math.max(...points.map(p => p.value)) / 5) * 5);
  const firstYear = Number(points[0].year);
  const yearSpan = Math.max(1, Number(points.at(-1)!.year) - firstYear);
  const x = (i: number) => 42 + (Number(points[i].year) - firstYear) * 618 / yearSpan;
  const y = (value: number) => 215 - value / max * 172;
  const line = points.map((p, i) => `${x(i)},${y(p.value)}`).join(" ");
  return <div>
    <div className={styles.chartToolbar}>
      <label>Explore a trend<select aria-label="Trend indicator" value={selected} onChange={e => { setSelected(e.target.value); setActive(null); }}>
        <option value="unemployment">Unemployment</option><option value="youth_unemployment">Youth unemployment</option><option value="participation">Labour force participation</option><option value="employment_ratio">Employment-to-population ratio</option>
      </select></label>
      <p className={styles.chartReadout} aria-live="polite"><strong>{point.value.toFixed(2)}%</strong><span>{point.year} observation</span></p>
    </div>
    <svg viewBox="0 0 700 255" className={styles.trend} role="img" aria-label={`${current.title}; ${points[0].year} to ${points.at(-1)?.year}`}>
      <defs><linearGradient id="market-trend-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7164ed" stopOpacity=".3"/><stop offset="100%" stopColor="#7164ed" stopOpacity=".015"/></linearGradient></defs>
      {[0, 1, 2, 3, 4].map(tick => <g key={tick}><line x1="42" x2="660" y1={y(max * tick / 4)} y2={y(max * tick / 4)} stroke="currentColor" opacity=".1"/><text x="31" y={y(max * tick / 4) + 4} textAnchor="end" fill="currentColor" fontSize="11">{(max * tick / 4).toFixed(1)}</text></g>)}
      <polygon points={`42,215 ${line} ${x(points.length - 1)},215`} fill="url(#market-trend-fill)"/>
      <polyline points={line} fill="none" stroke="#7164ed" strokeWidth="3" strokeLinejoin="round"/>
      {points.map((p, i) => <g key={p.year}>
        <circle cx={x(i)} cy={y(p.value)} r={active === i ? 6 : 4} fill="#7164ed" stroke="var(--card)" strokeWidth="2" tabIndex={0} role="img" aria-label={`${p.year}: ${p.value.toFixed(2)} percent`} onFocus={() => setActive(i)} onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)}><title>{`${p.year}: ${p.value.toFixed(2)}%`}</title></circle>
        {(i % 2 === 0 || i === points.length - 1) && <text x={x(i)} y="242" textAnchor="middle" fill="currentColor" fontSize="11">{p.year}</text>}
      </g>)}
    </svg>
    <p className={styles.caption}>Annual observations, not monthly changes. Hover or focus a point to inspect it. Missing observations are not replaced with zero.</p>
    <a className={styles.sourceLink} href={current.source_url}>Source: World Bank / ILO · {current.code} ↗</a>
    <details className={styles.dataTable}><summary>View chart data</summary><table><caption>{current.title}</caption><thead><tr><th>Year</th><th>Percent</th></tr></thead><tbody>{points.map(p => <tr key={p.year}><th>{p.year}</th><td>{p.value.toFixed(2)}%</td></tr>)}</tbody></table></details>
  </div>;
}
