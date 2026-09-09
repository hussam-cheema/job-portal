// Code-native editorial diagrams. No stock photography or third-party artwork.
import sharp from 'sharp';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const out = new URL('../public/blog/', import.meta.url);
await mkdir(out, { recursive: true });
const diagrams = [
  ['pps-salary-scale-2026', 'PPS SALARY SCALE · PAKISTAN 2026', 'Read the contract, then the number.', '#8b5cf6', ['01 · SCALE', '02 · STAGE', '03 · DEDUCTIONS', '04 · NET PAY'], ['Confirm the', 'Check approved', 'Use actual', 'Compare with'], ['PSDP package', 'pay fixation', 'payroll amounts', 'bank transfer']],
  ['bps-salary-chart-2026', 'BPS SALARY CHART · FEDERAL 2026', 'Basic pay is not take-home pay.', '#2563eb', ['BASIC PAY', '+ ALLOWANCES', '= GROSS PAY', '− DEDUCTIONS'], ['Grade and', 'Only authorized', 'Before payroll', 'Gives your'], ['approved stage', 'components', 'deductions', 'take-home pay']],
  ['new-pension-scheme-pakistan-2026', 'FEDERAL CIVILIAN PENSION · EXPLAINED', 'Contributions are not returns.', '#0d9488', ['10% EMPLOYEE', '12% EMPLOYER', '22% COMBINED', 'PENSION ACCOUNT'], ['Of pensionable', 'Of pensionable', 'Contribution', 'Reconcile your'], ['pay', 'pay', 'not yield', 'monthly credits']],
  ['fpsc-age-relaxation-2026', 'FPSC GENERAL RECRUITMENT · 2026', 'Four checks before you apply.', '#d97706', ['01 · NOTICE', '02 · DATE', '03 · RULE', '04 · PROOF'], ['Read the full', 'Use the exact', 'Do not count', 'Support the'], ['age wording', 'cutoff date', 'five years twice', 'category claim']],
  ['education-levels-pakistan', 'PAKISTAN EDUCATION · HEC CONTEXT', 'The level is only the first check.', '#4f46e5', ['14 YEARS', '16 YEARS', '18 YEARS', 'ELIGIBILITY'], ['Associate degree', 'Four-year BS', 'MS / MPhil', 'Level + subject'], ['common pathway', 'common pathway', 'common pathway', '+ recognition']],
];
const escape = s => s.replaceAll('&', '&amp;').replaceAll('<', '&lt;');
for (const [name, eyebrow, title, color, labels, lines, ends] of diagrams) {
  const cards = labels.map((label, i) => `<g transform="translate(${60+i*277},280)"><rect width="254" height="192" rx="18" fill="#ffffff"/><rect width="254" height="7" rx="3" fill="${color}"/><text x="20" y="48" font-size="19" font-weight="700" fill="${color}">${escape(label)}</text><text x="20" y="100" font-size="21" fill="#334155">${escape(lines[i])}</text><text x="20" y="133" font-size="21" fill="#334155">${escape(ends[i])}</text></g>`).join('');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630"><rect width="1200" height="630" fill="#0f172a"/><circle cx="1110" cy="50" r="240" fill="${color}" opacity=".16"/><g font-family="Arial, sans-serif"><text x="60" y="87" fill="#a5b4fc" font-size="21" font-weight="700" letter-spacing="2">${escape(eyebrow)}</text><text x="60" y="176" fill="white" font-size="44" font-weight="700">${escape(title)}</text><text x="60" y="222" fill="#cbd5e1" font-size="22">A practical guide · Check the official sources linked in the article</text>${cards}<text x="60" y="552" fill="#94a3b8" font-size="20">Pakistan Jobs Market · Editorial illustration, not an official notification</text></g></svg>`;
  await sharp(Buffer.from(svg)).png().toFile(fileURLToPath(new URL(`${name}.png`, out)));
}
