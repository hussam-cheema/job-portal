"""Reviewed, independently editable September 2026 guides."""
from pathlib import Path

ROOT = Path(__file__).parent
SPECS = [
    ("pps-salary-scale-2026-pakistan", "PPS Salary Scale 2026 Pakistan: PPS-1 to PPS-12, BPS Equivalence and Increments", "PPS Salary Scale 2026 Pakistan: PPS-1 to PPS-12", "PPS salary scale 2026 Pakistan", "01", "Compare Pakistan's PPS-1 to PPS-12 pay, BPS mapping and annual increments, with the official 2026 notification and practical contract salary examples.", ["PPS", "Project jobs", "Salary scales", "Pakistan"]),
    ("bps-salary-chart-2026-pakistan", "BPS Salary Chart 2026 Pakistan: BPS-1 to BPS-22, Allowances and Gross Pay", "BPS Salary Chart 2026 Pakistan: Pay and Allowances", "BPS salary chart 2026 Pakistan", "03", "Read the federal BPS-1 to BPS-22 salary chart for 2026, understand basic versus gross pay, and check allowances with official Finance Division sources.", ["BPS", "Government salary", "Allowances", "Pakistan"]),
    ("new-pension-scheme-pakistan-2026", "Pakistan's New Pension Scheme in 2026: Eligibility, Contributions and How It Works", "New Pension Scheme Pakistan 2026: Who Is Covered?", "new pension scheme Pakistan 2026", "05", "Understand Pakistan's federal contributory pension scheme, who it covers, employee and employer contributions, and what the 2026 implementation means.", ["Pension", "Government employees", "Retirement", "Pakistan"]),
    ("fpsc-age-relaxation-2026", "FPSC Age Relaxation 2026: General Five Years, Government Employees and Other Categories", "FPSC Age Relaxation 2026: Rules and Worked Examples", "FPSC age relaxation 2026", "07", "Check FPSC age relaxation in 2026 with worked examples, government service conditions, document checklists and the important difference from CSS rules.", ["FPSC", "Age relaxation", "Government jobs", "Eligibility"]),
    ("14-vs-16-vs-18-years-education-pakistan", "14 vs 16 vs 18 Years of Education in Pakistan: HEC Equivalence and Job Eligibility", "14 vs 16 vs 18 Years Education in Pakistan: HEC Guide", "14 vs 16 vs 18 years education Pakistan", "09", "Compare 14, 16 and 18 years of education in Pakistan, HEC equivalence, ADP, BS and MS qualifications, and how to check government job eligibility.", ["HEC", "Education equivalence", "Students", "Job eligibility"]),
]

SEPTEMBER_GUIDES = [dict(slug=slug, title=title, meta_title=meta, focus_keyword=keyword,
    edition_date=f"2026-09-{day}", excerpt=description, meta_description=description,
    meta_keywords=", ".join([keyword, *tags]), tags=tags, category="Career Guides",
    author="Pakistan Jobs Market Editorial Team", content=(ROOT / f"{slug}.html").read_text())
    for slug, title, meta, keyword, day, description, tags in SPECS]
