export type SalaryFamily =
  | "BPS"
  | "PPS"
  | "MP"
  | "SPPS"
  | "SPS"
  | "O"
  | "E"
  | "OG"
  | "EG"
  | "J"
  | "M";

export type PayBand = {
  min: number;
  increment: number;
  max: number;
  stages: number;
};

export type SalaryLine = { label: string; amount: number; note?: string };

export type SalaryResult = {
  lines: SalaryLine[];
  gross: number;
  annual: number;
  isOfficialSchedule: boolean;
};

export const FAMILY_OPTIONS: { value: SalaryFamily; label: string; detail: string }[] = [
  { value: "BPS", label: "BPS", detail: "Federal Basic Pay Scales 1–22" },
  { value: "PPS", label: "PPS", detail: "Project Pay Scales 1–12" },
  { value: "MP", label: "MP", detail: "Management Position Scales I–III" },
  { value: "SPPS", label: "SPPS", detail: "Special Professional Pay Scales I–III" },
  { value: "SPS", label: "SPS", detail: "Organization-specific Special Pay Scale" },
  { value: "O", label: "O", detail: "Organization-defined officer scale" },
  { value: "E", label: "E", detail: "Organization-defined employee/executive scale" },
  { value: "OG", label: "OG", detail: "Organization/banking officer grade" },
  { value: "EG", label: "EG", detail: "Organization executive grade" },
  { value: "J", label: "J", detail: "Organization-defined job grade" },
  { value: "M", label: "M", detail: "Management Grades I–III" },
];

export const BPS_2026: Record<number, PayBand> = {
  1: { min: 16280, increment: 520, max: 31880, stages: 30 }, 2: { min: 16600, increment: 590, max: 34300, stages: 30 },
  3: { min: 17130, increment: 700, max: 38130, stages: 30 }, 4: { min: 17650, increment: 800, max: 41650, stages: 30 },
  5: { min: 18300, increment: 910, max: 45600, stages: 30 }, 6: { min: 18930, increment: 1010, max: 49230, stages: 30 },
  7: { min: 19590, increment: 1100, max: 52590, stages: 30 }, 8: { min: 20290, increment: 1210, max: 56590, stages: 30 },
  9: { min: 20990, increment: 1310, max: 60290, stages: 30 }, 10: { min: 21680, increment: 1430, max: 64580, stages: 30 },
  11: { min: 22410, increment: 1580, max: 69810, stages: 30 }, 12: { min: 23750, increment: 1720, max: 75350, stages: 30 },
  13: { min: 25420, increment: 1880, max: 81820, stages: 30 }, 14: { min: 27060, increment: 2090, max: 89760, stages: 30 },
  15: { min: 28730, increment: 2380, max: 100130, stages: 30 }, 16: { min: 33720, increment: 2720, max: 115320, stages: 30 },
  17: { min: 54140, increment: 4110, max: 136340, stages: 20 }, 18: { min: 68330, increment: 5120, max: 170730, stages: 20 },
  19: { min: 105510, increment: 5450, max: 214510, stages: 20 }, 20: { min: 123090, increment: 8040, max: 235650, stages: 14 },
  21: { min: 136680, increment: 8920, max: 261560, stages: 14 }, 22: { min: 146770, increment: 10470, max: 293350, stages: 14 },
};

export const BPS_2022: Record<number, PayBand> = {
  1: { min: 13550, increment: 430, max: 26450, stages: 30 }, 2: { min: 13820, increment: 490, max: 28520, stages: 30 },
  3: { min: 14260, increment: 580, max: 31660, stages: 30 }, 4: { min: 14690, increment: 660, max: 34490, stages: 30 },
  5: { min: 15230, increment: 750, max: 37730, stages: 30 }, 6: { min: 15760, increment: 840, max: 40960, stages: 30 },
  7: { min: 16310, increment: 910, max: 43610, stages: 30 }, 8: { min: 16890, increment: 1000, max: 46890, stages: 30 },
  9: { min: 17470, increment: 1090, max: 50170, stages: 30 }, 10: { min: 18050, increment: 1190, max: 53750, stages: 30 },
  11: { min: 18650, increment: 1310, max: 57950, stages: 30 }, 12: { min: 19770, increment: 1430, max: 62670, stages: 30 },
  13: { min: 21160, increment: 1560, max: 67960, stages: 30 }, 14: { min: 22530, increment: 1740, max: 74730, stages: 30 },
  15: { min: 23920, increment: 1980, max: 83320, stages: 30 }, 16: { min: 28070, increment: 2260, max: 95870, stages: 30 },
  17: { min: 45070, increment: 3420, max: 113470, stages: 20 }, 18: { min: 56880, increment: 4260, max: 142080, stages: 20 },
  19: { min: 87840, increment: 4530, max: 178440, stages: 20 }, 20: { min: 102470, increment: 6690, max: 196130, stages: 14 },
  21: { min: 113790, increment: 7420, max: 217670, stages: 14 }, 22: { min: 122190, increment: 8710, max: 244130, stages: 14 },
};

export const BPS_2008_MIN: Record<number, number> = {
  1: 2970, 2: 3035, 3: 3140, 4: 3240, 5: 3340, 6: 3430, 7: 3530, 8: 3665, 9: 3820, 10: 3955,
  11: 4115, 12: 4355, 13: 4645, 14: 4920, 15: 5220, 16: 6060, 17: 9850, 18: 12910, 19: 19680,
  20: 23345, 21: 25880, 22: 27680,
};

export const PPS_2026: Record<number, PayBand> = {
  1: { min: 37800, increment: 1140, max: 43500, stages: 5 }, 2: { min: 47250, increment: 1420, max: 54350, stages: 5 },
  3: { min: 59070, increment: 1780, max: 67970, stages: 5 }, 4: { min: 70880, increment: 2130, max: 81530, stages: 5 },
  5: { min: 94500, increment: 2840, max: 108700, stages: 5 }, 6: { min: 141750, increment: 4260, max: 163050, stages: 5 },
  7: { min: 212630, increment: 6380, max: 244530, stages: 5 }, 8: { min: 295320, increment: 8860, max: 339620, stages: 5 },
  9: { min: 398130, increment: 11950, max: 457880, stages: 5 }, 10: { min: 568750, increment: 17070, max: 654100, stages: 5 },
  11: { min: 735000, increment: 22050, max: 845250, stages: 5 }, 12: { min: 1050000, increment: 31500, max: 1207500, stages: 5 },
};

export const MP_2023: Record<number, PayBand & { houseMin: number; houseMax: number; utilitiesMin: number; utilitiesMax: number; transport: number }> = {
  1: { min: 629230, increment: 47850, max: 772780, stages: 3, houseMin: 146450, houseMax: 205900, utilitiesMin: 28500, utilitiesMax: 35240, transport: 95910 },
  2: { min: 263180, increment: 39480, max: 421100, stages: 4, houseMin: 95700, houseMax: 159500, utilitiesMin: 11970, utilitiesMax: 19140, transport: 77430 },
  3: { min: 184230, increment: 26320, max: 263190, stages: 3, houseMin: 47850, houseMax: 63800, utilitiesMin: 8380, utilitiesMax: 11970, transport: 65060 },
};

export const SPPS: Record<number, PayBand> = {
  1: { min: 1500000, increment: 0, max: 2000000, stages: 0 },
  2: { min: 1000000, increment: 0, max: 1490000, stages: 0 },
  3: { min: 500000, increment: 0, max: 990000, stages: 0 },
};

export const MANAGEMENT_GRADES: Record<number, PayBand> = {
  1: { min: 82380, increment: 5870, max: 164560, stages: 14 },
  2: { min: 76720, increment: 5000, max: 146720, stages: 14 },
  3: { min: 69090, increment: 4510, max: 132230, stages: 14 },
};

export const ORGANIZATION_MAX_GRADES: Record<Exclude<SalaryFamily, "BPS" | "PPS" | "MP" | "SPPS" | "M">, number> = {
  SPS: 22,
  O: 20,
  E: 20,
  OG: 8,
  EG: 9,
  J: 20,
};

export function familyGrades(family: SalaryFamily): number[] {
  const max = family === "BPS" ? 22 : family === "PPS" ? 12 : family === "MP" || family === "SPPS" || family === "M" ? 3 : ORGANIZATION_MAX_GRADES[family];
  return Array.from({ length: max }, (_, index) => index + 1);
}
export function bandFor(family: SalaryFamily, grade: number): PayBand | null {
  if (family === "BPS") return BPS_2026[grade] || null;
  if (family === "PPS") return PPS_2026[grade] || null;
  if (family === "MP") return MP_2023[grade] || null;
  if (family === "SPPS") return SPPS[grade] || null;
  if (family === "M") return MANAGEMENT_GRADES[grade] || null;
  return null;
}

export function payAtStage(band: PayBand, stage: number): number {
  return Math.min(band.max, band.min + Math.max(0, Math.min(stage, band.stages)) * band.increment);
}

export function calculateGovernmentSalary(input: {
  family: SalaryFamily;
  grade: number;
  stage: number;
  bigCity: boolean;
  packageAmount: number;
  additionalAllowances: number;
  dra2026: boolean;
  disabledConveyance: boolean;
}): SalaryResult {
  const { family, grade, stage, bigCity, packageAmount, additionalAllowances, dra2026, disabledConveyance } = input;
  const lines: SalaryLine[] = [];
  if (family === "BPS") {
    const band = BPS_2026[grade];
    const oldBand = BPS_2022[grade];
    const basic = payAtStage(band, stage);
    const frozenBasic = payAtStage(oldBand, stage);
    const houseRent = Math.round(BPS_2008_MIN[grade] * (bigCity ? 0.45 : 0.3) * 1.5);
    const conveyance = grade <= 4 ? 2678 : grade <= 10 ? 2898 : grade <= 15 ? 4284 : 7500;
    const medical = grade <= 15 ? 1500 : Math.max(1500, Math.round(BPS_2008_MIN[grade] * 0.1875));
    lines.push(
      { label: "Basic pay (BPS 2026)", amount: basic, note: `Stage ${stage} of ${band.stages}` },
      { label: "House rent allowance", amount: houseRent, note: bigCity ? "Declared big-city rate" : "Other-city rate" },
      { label: "Conveyance allowance", amount: conveyance },
      { label: "Medical allowance", amount: medical },
      { label: "Ad-hoc Relief Allowance 2023", amount: Math.round(frozenBasic * (grade <= 16 ? 0.35 : 0.3)), note: "Frozen on BPS 2022 pay point" },
      { label: "Ad-hoc Relief Allowance 2024", amount: Math.round(frozenBasic * (grade <= 16 ? 0.25 : 0.2)), note: "Frozen on BPS 2022 pay point" },
      { label: "Ad-hoc Relief Allowance 2026", amount: Math.round(basic * 0.07), note: "7% of running BPS 2026 basic" },
    );
    if (dra2026) lines.push({ label: "Disparity Reduction Allowance 2026", amount: Math.round(frozenBasic * 0.15), note: "Only for employees already receiving DRA" });
    if (disabledConveyance) lines.push({ label: "Special conveyance allowance", amount: 10000, note: "Eligible disabled employee" });
  } else if (family === "PPS") {
    const band = PPS_2026[grade];
    lines.push({ label: "PPS lump-sum package", amount: payAtStage(band, stage), note: `Stage ${stage} of ${band.stages}; no additional facility under the standard package` });
  } else if (family === "MP") {
    const band = MP_2023[grade];
    const ratio = band.stages ? Math.max(0, Math.min(stage, band.stages)) / band.stages : 0;
    lines.push(
      { label: "Basic pay", amount: payAtStage(band, stage), note: `MP-${["I", "II", "III"][grade - 1]}, stage ${stage}` },
      { label: "House rent", amount: Math.round(band.houseMin + (band.houseMax - band.houseMin) * ratio) },
      { label: "Utilities", amount: Math.round(band.utilitiesMin + (band.utilitiesMax - band.utilitiesMin) * ratio) },
      { label: "Monetized transport", amount: band.transport },
    );
  } else if (family === "SPPS") {
    const band = SPPS[grade];
    const amount = Math.min(band.max, Math.max(band.min, packageAmount || band.min));
    lines.push({ label: "All-inclusive SPPS package", amount, note: `Official published range: PKR ${band.min.toLocaleString("en-PK")}–${band.max.toLocaleString("en-PK")}` });
  } else if (family === "M") {
    const band = MANAGEMENT_GRADES[grade];
    lines.push({ label: "Management Grade basic pay", amount: payAtStage(band, stage), note: `M-${["I", "II", "III"][grade - 1]}, published federal management scale` });
  } else {
    lines.push({ label: `${family}-${grade} organization package`, amount: Math.max(0, packageAmount), note: "Enter the official amount from the employing organization's document" });
  }
  if (additionalAllowances > 0) lines.push({ label: "Other verified monthly allowances", amount: additionalAllowances, note: "Entered by user from salary slip or appointment terms" });
  const gross = lines.reduce((sum, line) => sum + line.amount, 0);
  return { lines, gross, annual: gross * 12, isOfficialSchedule: !["SPS", "O", "E", "OG", "EG", "J"].includes(family) };
}
