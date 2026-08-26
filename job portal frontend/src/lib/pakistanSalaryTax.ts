export const TAX_YEARS = [
  "2026-2027", "2025-2026", "2024-2025", "2023-2024", "2022-2023",
  "2021-2022", "2020-2021", "2019-2020", "2018-2019", "2017-2018",
  "2016-2017", "2015-2016", "2014-2015",
] as const;

export type TaxYear = (typeof TAX_YEARS)[number];

type Slab = { upTo: number; base: number; threshold: number; rate: number };

const slabs = (annualIncome: number, rows: Slab[]) => {
  const row = rows.find((item) => annualIncome <= item.upTo) || rows[rows.length - 1];
  return row.base + Math.max(0, annualIncome - row.threshold) * row.rate;
};

/** Estimate federal income tax for a Pakistan resident salaried individual. */
export function calculateAnnualSalaryTax(annualIncome: number, year: TaxYear): number {
  const income = Math.max(0, Number.isFinite(annualIncome) ? annualIncome : 0);
  let tax = 0;

  if (year === "2026-2027") {
    tax = slabs(income, [
      { upTo: 600_000, base: 0, threshold: 0, rate: 0 },
      { upTo: 1_200_000, base: 0, threshold: 600_000, rate: 0.01 },
      { upTo: 2_200_000, base: 6_000, threshold: 1_200_000, rate: 0.11 },
      { upTo: 3_200_000, base: 116_000, threshold: 2_200_000, rate: 0.20 },
      { upTo: 4_100_000, base: 316_000, threshold: 3_200_000, rate: 0.25 },
      { upTo: 5_600_000, base: 541_000, threshold: 4_100_000, rate: 0.29 },
      { upTo: 7_000_000, base: 976_000, threshold: 5_600_000, rate: 0.32 },
      { upTo: Infinity, base: 1_424_000, threshold: 7_000_000, rate: 0.35 },
    ]);
  } else if (year === "2025-2026") {
    tax = slabs(income, [
      { upTo: 600_000, base: 0, threshold: 0, rate: 0 },
      { upTo: 1_200_000, base: 0, threshold: 600_000, rate: 0.01 },
      { upTo: 2_200_000, base: 6_000, threshold: 1_200_000, rate: 0.11 },
      { upTo: 3_200_000, base: 116_000, threshold: 2_200_000, rate: 0.23 },
      { upTo: 4_100_000, base: 346_000, threshold: 3_200_000, rate: 0.30 },
      { upTo: Infinity, base: 616_000, threshold: 4_100_000, rate: 0.35 },
    ]);
    if (income > 10_000_000) tax *= 1.09;
  } else if (year === "2024-2025") {
    tax = slabs(income, [
      { upTo: 600_000, base: 0, threshold: 0, rate: 0 },
      { upTo: 1_200_000, base: 0, threshold: 600_000, rate: 0.05 },
      { upTo: 2_200_000, base: 30_000, threshold: 1_200_000, rate: 0.15 },
      { upTo: 3_200_000, base: 180_000, threshold: 2_200_000, rate: 0.25 },
      { upTo: 4_100_000, base: 430_000, threshold: 3_200_000, rate: 0.30 },
      { upTo: Infinity, base: 700_000, threshold: 4_100_000, rate: 0.35 },
    ]);
    if (income > 10_000_000) tax *= 1.10;
  } else if (year === "2023-2024") {
    tax = slabs(income, [
      { upTo: 600_000, base: 0, threshold: 0, rate: 0 },
      { upTo: 1_200_000, base: 0, threshold: 600_000, rate: 0.025 },
      { upTo: 2_400_000, base: 15_000, threshold: 1_200_000, rate: 0.125 },
      { upTo: 3_600_000, base: 165_000, threshold: 2_400_000, rate: 0.225 },
      { upTo: 6_000_000, base: 435_000, threshold: 3_600_000, rate: 0.275 },
      { upTo: Infinity, base: 1_095_000, threshold: 6_000_000, rate: 0.35 },
    ]);
  } else if (year === "2022-2023") {
    tax = slabs(income, [
      { upTo: 600_000, base: 0, threshold: 0, rate: 0 },
      { upTo: 1_200_000, base: 0, threshold: 600_000, rate: 0.025 },
      { upTo: 2_400_000, base: 15_000, threshold: 1_200_000, rate: 0.125 },
      { upTo: 3_600_000, base: 165_000, threshold: 2_400_000, rate: 0.20 },
      { upTo: 6_000_000, base: 405_000, threshold: 3_600_000, rate: 0.25 },
      { upTo: 12_000_000, base: 1_005_000, threshold: 6_000_000, rate: 0.325 },
      { upTo: Infinity, base: 2_955_000, threshold: 12_000_000, rate: 0.35 },
    ]);
  } else if (["2019-2020", "2020-2021", "2021-2022"].includes(year)) {
    tax = slabs(income, [
      { upTo: 600_000, base: 0, threshold: 0, rate: 0 },
      { upTo: 1_200_000, base: 0, threshold: 600_000, rate: 0.05 },
      { upTo: 1_800_000, base: 30_000, threshold: 1_200_000, rate: 0.10 },
      { upTo: 2_500_000, base: 90_000, threshold: 1_800_000, rate: 0.15 },
      { upTo: 3_500_000, base: 195_000, threshold: 2_500_000, rate: 0.175 },
      { upTo: 5_000_000, base: 370_000, threshold: 3_500_000, rate: 0.20 },
      { upTo: 8_000_000, base: 670_000, threshold: 5_000_000, rate: 0.225 },
      { upTo: 12_000_000, base: 1_345_000, threshold: 8_000_000, rate: 0.25 },
      { upTo: 30_000_000, base: 2_345_000, threshold: 12_000_000, rate: 0.275 },
      { upTo: 50_000_000, base: 7_295_000, threshold: 30_000_000, rate: 0.30 },
      { upTo: 75_000_000, base: 13_295_000, threshold: 50_000_000, rate: 0.325 },
      { upTo: Infinity, base: 21_420_000, threshold: 75_000_000, rate: 0.35 },
    ]);
  } else if (year === "2018-2019") {
    if (income <= 400_000) tax = 0;
    else if (income <= 800_000) tax = 1_000;
    else if (income <= 1_200_000) tax = 2_000;
    else if (income <= 2_500_000) tax = Math.max(2_000, (income - 1_200_000) * 0.05);
    else if (income <= 4_000_000) tax = 65_000 + (income - 2_500_000) * 0.15;
    else if (income <= 8_000_000) tax = 290_000 + (income - 4_000_000) * 0.20;
    else tax = 1_090_000 + (income - 8_000_000) * 0.25;
  } else if (["2015-2016", "2016-2017", "2017-2018"].includes(year)) {
    tax = slabs(income, [
      { upTo: 400_000, base: 0, threshold: 0, rate: 0 },
      { upTo: 500_000, base: 0, threshold: 400_000, rate: 0.02 },
      { upTo: 750_000, base: 2_000, threshold: 500_000, rate: 0.05 },
      { upTo: 1_400_000, base: 14_500, threshold: 750_000, rate: 0.10 },
      { upTo: 1_500_000, base: 79_500, threshold: 1_400_000, rate: 0.125 },
      { upTo: 1_800_000, base: 92_000, threshold: 1_500_000, rate: 0.15 },
      { upTo: 2_500_000, base: 137_000, threshold: 1_800_000, rate: 0.175 },
      { upTo: 3_000_000, base: 259_500, threshold: 2_500_000, rate: 0.20 },
      { upTo: 3_500_000, base: 359_500, threshold: 3_000_000, rate: 0.225 },
      { upTo: 4_000_000, base: 472_000, threshold: 3_500_000, rate: 0.25 },
      { upTo: 7_000_000, base: 597_000, threshold: 4_000_000, rate: 0.275 },
      { upTo: Infinity, base: 1_422_000, threshold: 7_000_000, rate: 0.30 },
    ]);
  } else {
    tax = slabs(income, [
      { upTo: 400_000, base: 0, threshold: 0, rate: 0 },
      { upTo: 750_000, base: 0, threshold: 400_000, rate: 0.05 },
      { upTo: 1_400_000, base: 17_500, threshold: 750_000, rate: 0.10 },
      { upTo: 1_500_000, base: 82_500, threshold: 1_400_000, rate: 0.125 },
      { upTo: 1_800_000, base: 95_000, threshold: 1_500_000, rate: 0.15 },
      { upTo: 2_500_000, base: 140_000, threshold: 1_800_000, rate: 0.175 },
      { upTo: 3_000_000, base: 262_500, threshold: 2_500_000, rate: 0.20 },
      { upTo: 3_500_000, base: 362_500, threshold: 3_000_000, rate: 0.225 },
      { upTo: 4_000_000, base: 475_000, threshold: 3_500_000, rate: 0.25 },
      { upTo: 7_000_000, base: 600_000, threshold: 4_000_000, rate: 0.275 },
      { upTo: Infinity, base: 1_425_000, threshold: 7_000_000, rate: 0.30 },
    ]);
  }
  return Math.round(Math.max(0, tax));
}

export function calculateSalaryTax(monthlyIncome: number, year: TaxYear) {
  const monthly = Math.max(0, Number.isFinite(monthlyIncome) ? monthlyIncome : 0);
  const annualIncome = monthly * 12;
  const annualTax = calculateAnnualSalaryTax(annualIncome, year);
  const monthlyTax = Math.round(annualTax / 12);
  return {
    monthlyIncome: monthly,
    monthlyTax,
    monthlyAfterTax: Math.max(0, monthly - monthlyTax),
    annualIncome,
    annualTax,
    annualAfterTax: Math.max(0, annualIncome - annualTax),
  };
}
