"use client";

import { useEffect, useMemo, useState } from "react";
import {
  FAMILY_OPTIONS,
  SPPS,
  bandFor,
  calculateGovernmentSalary,
  familyGrades,
  type SalaryFamily,
} from "@/lib/governmentSalary";

const money = new Intl.NumberFormat("en-PK", { maximumFractionDigits: 0 });
const roman = ["I", "II", "III"];

const sources: Record<SalaryFamily, { title: string; href: string; detail: string }[]> = {
  BPS: [
    { title: "Finance Division — Basic Pay Scales 2026", href: "https://finance.gov.pk/circulars/REVISION_OF_BASIC_PAY_SCALES_2026.pdf", detail: "BPS 1–22 pay points and 7% Ad-hoc Relief Allowance 2026." },
    { title: "Finance Division — Conveyance Allowance 2026", href: "https://finance.gov.pk/circulars/REVISION_IN_THE_RATES_OF_CONVEYANCE_ALLOWANCE_BPS_1_22.pdf", detail: "Current BPS 1–22 conveyance rates." },
    { title: "Finance Division — House Rent Allowance", href: "https://www.finance.gov.pk/circulars/circular_02072018_4.pdf", detail: "Frozen big-city and other-city HRA basis." },
    { title: "Finance Division — General Orders", href: "https://www.finance.gov.pk/publications/Compilation_of_General_Orders.pdf", detail: "Medical allowance and historical BPS 2008 reference amounts." },
    { title: "Finance Division — 2023 relief", href: "https://finance.gov.pk/circulars/circular_04072023_1.pdf", detail: "ARA 2023 rates for BPS 1–22." },
    { title: "Finance Division — 2024 relief", href: "https://www.finance.gov.pk/circulars/circular_10072024_1.pdf", detail: "ARA 2024 rates for BPS 1–22." },
    { title: "Finance Division — 2026 DRA", href: "https://finance.gov.pk/circulars/GRANT_OF_DISPARITY_REDUCTION_ALLOWANCE_2026.pdf", detail: "Optional 15% DRA for employees already receiving DRA." },
  ],
  PPS: [{ title: "Finance Division — Standard Pay Package 2026", href: "https://finance.gov.pk/circulars/circular_05042026.pdf", detail: "PPS 1–12 minimum, increment, maximum and no-additional-facility condition." }],
  MP: [{ title: "Finance Division — MP Scales 2023", href: "https://finance.gov.pk/circulars/circular_31102023.pdf", detail: "MP-I to MP-III basic pay, house rent, utilities and monetized transport." }],
  SPPS: [{ title: "Finance Division — SPPS vacancy schedule", href: "https://www.finance.gov.pk/jobs/adv_19052024_1.pdf", detail: "Official all-inclusive remuneration bands for SPPS-I to SPPS-III." }],
  M: [{ title: "Finance Division — Management Grades", href: "https://finance.gov.pk/publications/YearBook2018_19.pdf", detail: "Published M-I to M-III management scales." }],
  SPS: [{ title: "BISP — official SPS recruitment example", href: "https://bisp.gov.pk/SiteImage/Misc/files/Advertisement%20Various%20BISP%20Positions%20on%20Contract%20_02012021.pdf", detail: "Shows that SPS grades and packages belong to the issuing organization; they are not one central federal salary table." }],
  O: [{ title: "Finance Division — public-sector corporation pay schemes", href: "https://www.finance.gov.pk/publications/Various_Schemes_of_Pay_Scales.pdf", detail: "Organization scales and perquisites are governed by the relevant corporation's approved scheme." }],
  E: [{ title: "Finance Division — public-sector corporation pay schemes", href: "https://www.finance.gov.pk/publications/Various_Schemes_of_Pay_Scales.pdf", detail: "Organization scales and perquisites are governed by the relevant corporation's approved scheme." }],
  OG: [{ title: "State Bank of Pakistan — Staff Regulations", href: "https://www.sbp.org.pk/about/s_regulations/staff-regu.pdf", detail: "SBP's own OG classification illustrates why an OG amount must come from the employer's current document." }],
  EG: [{ title: "Senate of Pakistan — OGDCL grading record", href: "https://www.senate.gov.pk/uploads/documents/debates/1627625914_802.pdf", detail: "Official record identifies OGDCL's separate EG-I to EG-IX structure." }],
  J: [{ title: "Finance Division — public-sector corporation pay schemes", href: "https://www.finance.gov.pk/publications/Various_Schemes_of_Pay_Scales.pdf", detail: "Job-grade packages are organization-specific and must be taken from the issuing body's approved terms." }],
};

export function GovernmentSalaryCalculator() {
  const [family, setFamily] = useState<SalaryFamily>("BPS");
  const [grade, setGrade] = useState(1);
  const [stage, setStage] = useState(0);
  const [bigCity, setBigCity] = useState(true);
  const [packageAmount, setPackageAmount] = useState(0);
  const [additionalAllowances, setAdditionalAllowances] = useState(0);
  const [dra2026, setDra2026] = useState(false);
  const [disabledConveyance, setDisabledConveyance] = useState(false);
  const grades = useMemo(() => familyGrades(family), [family]);
  const selectedGrade = grades.includes(grade) ? grade : grades[0];
  const band = bandFor(family, selectedGrade);
  const organizationSpecific = ["SPS", "O", "E", "OG", "EG", "J"].includes(family);

  useEffect(() => {
    setGrade(1);
    setStage(0);
    setPackageAmount(family === "SPPS" ? SPPS[1].min : 0);
  }, [family]);

  useEffect(() => {
    setStage(0);
    if (family === "SPPS") setPackageAmount((SPPS[selectedGrade] || SPPS[1]).min);
  }, [family, selectedGrade]);

  const result = useMemo(() => calculateGovernmentSalary({ family, grade: selectedGrade, stage, bigCity, packageAmount, additionalAllowances, dra2026, disabledConveyance }), [family, selectedGrade, stage, bigCity, packageAmount, additionalAllowances, dra2026, disabledConveyance]);
  const gradeLabel = (value: number) => ["MP", "SPPS", "M"].includes(family) ? roman[value - 1] : String(value);

  return (
    <div className="calculator-shell government-salary-calculator" data-testid="government-salary-calculator">
      <div className="calculator-intro">
        <p className="tool-kicker">Pakistan government pay estimator</p>
        <h2>Build a transparent salary breakdown</h2>
        <p>Select a scale, grade and pay point. Centrally published schedules calculate automatically; organization-defined grades use the official amount you enter.</p>
      </div>

      <div className="government-salary-form">
        <section className="government-salary-section">
          <div className="government-salary-section-title"><span>01</span><div><h3>Pay scale and grade</h3><p>Choose the scale exactly as shown in the vacancy or appointment letter.</p></div></div>
          <div className="calculator-input-grid government-salary-inputs">
            <label><span>Pay scale</span><select aria-label="Pay scale" value={family} onChange={(event) => setFamily(event.target.value as SalaryFamily)}>{FAMILY_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label} — {item.detail}</option>)}</select></label>
            <label><span>Grade</span><select aria-label="Government grade" value={selectedGrade} onChange={(event) => setGrade(Number(event.target.value))}>{grades.map((item) => <option key={item} value={item}>{family}-{gradeLabel(item)}</option>)}</select></label>
            {band && band.stages > 0 && <label><span>Pay stage / completed increments</span><select aria-label="Pay stage" value={stage} onChange={(event) => setStage(Number(event.target.value))}>{Array.from({ length: band.stages + 1 }, (_, item) => <option key={item} value={item}>Stage {item} — PKR {money.format(Math.min(band.max, band.min + item * band.increment))}</option>)}</select></label>}
            {(organizationSpecific || family === "SPPS") && <label><span>{family === "SPPS" ? "Agreed package within official band" : "Official monthly package / basic pay"} (PKR)</span><input aria-label="Official package amount" type="number" min="0" step="1000" value={packageAmount || ""} placeholder="Enter amount from official document" onChange={(event) => setPackageAmount(Math.max(0, Number(event.target.value) || 0))} /></label>}
          </div>
          {organizationSpecific && <aside className="government-salary-inline-note"><strong>{family} is not a single nationwide monetary scale.</strong> Grade labels, maximum grade and benefits can differ by employer. The selector covers the published/common range, while the amount must come from that organization&apos;s current official advertisement, appointment letter or salary slip.</aside>}
        </section>

        <section className="government-salary-section">
          <div className="government-salary-section-title"><span>02</span><div><h3>Allowances and eligibility</h3><p>Only benefits supported by the selected schedule are added automatically.</p></div></div>
          {family === "BPS" && <div className="government-salary-toggles">
            <label><input type="radio" name="posting-city" checked={bigCity} onChange={() => setBigCity(true)} /><span><strong>Declared big city</strong><small>45% frozen HRA basis, increased by 50%</small></span></label>
            <label><input type="radio" name="posting-city" checked={!bigCity} onChange={() => setBigCity(false)} /><span><strong>Other city</strong><small>30% frozen HRA basis, increased by 50%</small></span></label>
            <label><input type="checkbox" checked={dra2026} onChange={(event) => setDra2026(event.target.checked)} /><span><strong>Eligible for DRA 2026</strong><small>Only if already receiving Disparity Reduction Allowance</small></span></label>
            <label><input type="checkbox" checked={disabledConveyance} onChange={(event) => setDisabledConveyance(event.target.checked)} /><span><strong>Special conveyance eligible</strong><small>Eligible disabled federal employee</small></span></label>
          </div>}
          <div className="calculator-input-grid government-salary-inputs single-input"><label><span>Other verified monthly allowances (PKR)</span><input aria-label="Other monthly allowances" type="number" min="0" step="500" value={additionalAllowances || ""} placeholder="0" onChange={(event) => setAdditionalAllowances(Math.max(0, Number(event.target.value) || 0))} /></label></div>
        </section>
      </div>

      <section className="government-salary-results" aria-live="polite">
        <div className="government-salary-summary"><div><span>Estimated monthly gross</span><strong>PKR {money.format(result.gross)}</strong></div><div><span>Estimated annual gross</span><strong>PKR {money.format(result.annual)}</strong></div></div>
        <div className="government-salary-breakdown"><div className="government-salary-breakdown-head"><h3>Monthly salary breakdown</h3><span>{result.isOfficialSchedule ? "Published schedule" : "Organization amount required"}</span></div>{result.lines.map((line) => <div className="government-salary-row" key={line.label}><div><strong>{line.label}</strong>{line.note && <small>{line.note}</small>}</div><b>PKR {money.format(line.amount)}</b></div>)}<div className="government-salary-row total"><div><strong>Gross monthly salary</strong><small>Before tax, provident fund and other deductions</small></div><b>PKR {money.format(result.gross)}</b></div></div>
      </section>

      <aside className="calculator-note"><strong>Payroll estimate, not an appointment entitlement.</strong> Posting, department, date of appointment, government accommodation, personal pay, frozen allowances, deputation, tax and deductions can change the actual payslip. Verify the result with the employing organization or accounts office.</aside>
      <section className="government-salary-sources"><p className="tool-kicker">Official references for {family}</p><h3>Source documents</h3><div>{sources[family].map((source) => <a key={source.href} href={source.href} target="_blank" rel="noreferrer"><strong>{source.title}<span aria-hidden="true">↗</span></strong><small>{source.detail}</small></a>)}</div></section>
    </div>
  );
}
