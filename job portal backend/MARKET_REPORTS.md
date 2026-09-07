# National job-market reports

The public `/dashboard` is about Pakistan nationally, not site traffic or the
site's share of recruiting. All main metrics use the official World Bank WDI
API (source 2, country PAK), with ILO modelled-estimate attribution. A small
separate footer contains the preceding calendar month's site listing counts.

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
