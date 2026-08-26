"use client";

import { useMemo, useState } from "react";
import { calculateSalaryTax, TAX_YEARS, type TaxYear } from "@/lib/pakistanSalaryTax";

const money = new Intl.NumberFormat("en-PK", { maximumFractionDigits: 0 });

export function PakistanTaxCalculator() {
  const [salary, setSalary] = useState(100_000);
  const [year, setYear] = useState<TaxYear>("2026-2027");
  const result = useMemo(() => calculateSalaryTax(salary, year), [salary, year]);
  const rows = [
    ["Monthly income", result.monthlyIncome],
    ["Monthly tax", result.monthlyTax],
    ["Salary after tax", result.monthlyAfterTax],
    ["Yearly income", result.annualIncome],
    ["Yearly tax", result.annualTax],
    ["Yearly income after tax", result.annualAfterTax],
  ] as const;

  return (
    <div className="calculator-shell tax-calculator" data-testid="tax-calculator">
      <div className="calculator-intro">
        <p className="tool-kicker">Pakistan salary estimator</p>
        <h2>See your take-home salary</h2>
        <p>Enter gross monthly taxable salary and choose a federal tax year.</p>
      </div>
      <div className="calculator-input-grid">
        <label><span>Monthly salary (PKR)</span><input aria-label="Monthly salary" type="number" min="0" step="1000" value={salary || ""} onChange={(event) => setSalary(Math.max(0, Number(event.target.value) || 0))} /></label>
        <label><span>Tax year</span><select aria-label="Tax year" value={year} onChange={(event) => setYear(event.target.value as TaxYear)}>{TAX_YEARS.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      </div>
      <div className="tax-result-grid" aria-live="polite">
        {rows.map(([label, value], index) => <div key={label} className={index === 2 || index === 5 ? "tax-result-highlight" : ""}><span>{label}</span><strong>PKR {money.format(value)}</strong></div>)}
      </div>
      <aside className="calculator-note">
        <strong>Estimate, not tax advice.</strong> This calculator covers federal slabs for a resident salaried individual. Exemptions, credits, benefits, rebates and special income are not included. Verify a filing or payroll decision with FBR or a qualified tax adviser.
      </aside>
      <p className="calculator-sources">Rules checked against <a href="https://www.fbr.gov.pk/Categ/Finance-Acts/620" target="_blank" rel="noreferrer">FBR Finance Acts</a> and the <a href="https://www.fbr.gov.pk/withholding-taxes-rate-card/174298/174301" target="_blank" rel="noreferrer">FBR withholding tax rate cards</a>.</p>
    </div>
  );
}
