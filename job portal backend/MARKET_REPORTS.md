# National job-market reports

The public `/dashboard` is about Pakistan nationally, not site traffic or the
site's share of recruiting. Trend and rate metrics use the official World Bank
WDI API (source 2, country PAK), with ILO attribution. Occupation and province
graphs use the separate PBS Labour Force Survey. A small separate footer shows
current overall/monthly website listing counts and expandable website graphs.

## Occupation and province graphs

- `GET /api/market-reports/national-breakdowns` serves the reviewed PBS LFS
  2024-25 snapshot in `employment_breakdowns.py`: Tables 4.1 (printed page 37)
  and 4.7 (printed page 43), 19th ICLS, employed persons aged 10+. Values were
  checked against the official PDF, including rounding discrepancies.
- PBS is a versioned, manually reviewed survey dataset, not a live monthly
  feed. New survey releases require a reviewed dataset update. The monthly
  publisher preserves the current PBS version inside future editions; existing
  archives are never backfilled. The current dashboard can display this newer,
  separately dated survey detail alongside its original monthly edition.
- Website graphs count advertisements, not positions or employed people.
  Occupations use explicit occupational tags only; ambiguous/missing tags stay
  in Multiple occupation groups/Unclassified. Government/private and employer
  names are not occupational categories. No stored job or taxonomy is changed.
- Each advertisement counts once in each applicable province. Nationwide ads
  have their own bucket; multi-province bars must not be summed as unique jobs.
  Known cities override contradictory province tags. Totals and graph buckets
  use the same lightweight job query, including expired advertisements.

## Automatic publishing

- The existing Railway newsletter cron (`railway.newsletter.toml`, every 15
  minutes) also invokes the market-report publisher, even if email delivery
  fails. No extra subscription, credential, or paid data provider is required.
- The API runs the same check after startup and every 15 minutes as a fallback.
- The first successful run in each **Asia/Karachi** calendar month publishes one
  edition. On initial release it publishes the current month immediately.
- PostgreSQL transaction advisory lock 714209031 and the `market_reports.month`
  primary key prevent concurrent duplicate publication. Source errors are logged
  and retried on the next scheduler run. Existing reports remain available.
- The new table is created by the existing `init_db()` / SQLAlchemy startup
  migration. Neither existing jobs nor newsletter records are modified.
- Manual retry: `python -m app.commands.market_reports` in the API environment.
  It is idempotent and cannot overwrite an already published edition.

## Data integrity

`market_reports.data` stores the full normalized national series, indicator
titles/codes and URLs, provider update date, retrieval time, a SHA-256 data
fingerprint, and the small site supplement. Public JSON routes:

- `GET /api/market-reports`: all published edition summaries, newest first.
- `GET /api/market-reports/YYYY-MM`: immutable report data.
- `GET /api/market-reports/site-statistics`: current website listing totals and
  all publication-month breakdowns, cached for five minutes. Includes expired
  advertisements; counts advertisements, not vacancies. Undated records appear
  in overall totals separately from month buckets. A zero current-month bucket
  is always present. The dashboard footer uses this live read-only aggregation,
  not the original previous-month snapshot embedded in archived reports.

The source importer follows complete pagination, validates country, indicator,
year and finite 0–100 percent values, preserves true zeros, and rejects missing
series. It does not silently publish partial or cached national data on failure.
The fixed source host/indicator allowlist cannot be changed by public requests.
No publisher work or database writes run in response to public report requests.

National observations are **annual**, although editions are monthly. Each card
and chart shows the observation year. Gender and sector comparisons require a
common year. The main trend exposes the last 12 available annual observations
from series retrieved from 2000 onward. Repeated unchanged official data is
explicitly labelled. Chart values are rounded for display, not in storage.

Reports before the launch are not fabricated: a current data revision cannot
reconstruct an earlier publication vintage. The archive grows monthly from the
first actual publication; historical annual trends are available immediately.
If a whole month is missed during an outage, it is not falsely backdated later.

## Release checks

Run backend tests, frontend lint/build with the mock API, and
`e2e/market-dashboard.spec.ts` plus the public responsive suite. Production must
return a real edition with 14 cited indicators before the release is considered
complete. Confirm `/dashboard`, its monthly archive URL, and `/sitemap.xml`.
The production frontend is built separately against the production API;
synthetic e2e fixtures are not application imports or production seed data.
