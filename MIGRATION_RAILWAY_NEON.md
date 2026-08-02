# Azure to Railway + Neon migration runbook

The production migration has **8 total steps**. Azure remains live and is the
rollback target until step 8. Public visitors keep read access during the final
copy; only writes are briefly paused.

1. **Audit** — verify Azure PostgreSQL version/networking, Container App
   configuration, domains, and environment-variable inventory.
2. **Application portability** — use Neon's pooled runtime URL with
   `DB_POOL_MODE=serverless`, disable persistent SQLAlchemy connections, and add
   the controlled `WRITE_FREEZE_ENABLED` switch.
3. **Railway packaging** — deploy one API service and one 15-minute newsletter
   cron service. The API image includes the fallback embedding model, avoiding
   an attached volume and preserving overlapping deployments.
4. **Database transfer safety** — build the PostgreSQL 16 migration image and
   run it as a temporary Azure Container Apps Job inside the existing VNet. It
   uses a transaction-consistent dump, restores only `public`, and verifies
   table names plus exact row counts.
5. **Tests** — run backend tests, frontend lint/build/e2e, Docker image checks,
   migration safety tests, and production-style readiness tests.
6. **Parallel provisioning** — create Neon PostgreSQL **16** in Singapore with
   Neon Auth disabled; create Railway API and cron services in Singapore; copy
   secrets and non-secret variables without changing production traffic.
7. **Near-zero-downtime cutover**:
   - perform an initial copy while Azure serves production;
   - validate Railway's generated domain against Neon;
   - enable the write freeze on both backends;
   - perform the final small copy and parity check;
   - attach/activate `api.pakistanjobsmarket.com` on Railway;
   - verify health, reads, authentication, uploads, newsletter outbox, and logs;
   - disable the write freeze on Railway.
8. **Rollback window and retirement** — keep the Azure Container App and
   PostgreSQL server intact until every retirement gate below passes. Then
   remove only the retired backend/database resources. Azure Static Web Apps
   remains the production frontend.

## Current production topology

- Public frontend: Azure Static Web Apps (`job-portal-web`).
- Public API: Railway Serverless through `api.pakistanjobsmarket.com`.
- Database: Neon PostgreSQL 16 using the pooled URL at runtime.
- Object storage and independent database backups: Cloudflare R2.
- Newsletter retry worker: Railway cron, every 15 minutes.
- DNS and edge TLS: Cloudflare.

The GitHub workflow no longer deploys Azure Container Apps. A push to `main`
runs backend and frontend checks and deploys the Azure Static Web Apps
frontend. Railway's GitHub integration builds the API and newsletter services
from `main`; changes under `migration/` also publish the disposable migration
image through the separate migration-image workflow.

## Step 8 retirement gates

Do not delete Azure PostgreSQL or Container Apps until all of these are true:

1. Public production verification passes for the Railway API and frontend.
2. Authenticated create/read/update/delete checks pass for jobs, blogs, pages,
   taxonomy, subscribers, settings, and disposable uploads.
3. Railway API and newsletter cron are healthy and use Neon.
4. `api.pakistanjobsmarket.com` resolves to Railway and TLS is valid.
5. A fresh custom-format PostgreSQL backup is uploaded to R2 with its SHA-256
   checksum, and the remote object size is verified.
6. The Neon direct URL is saved outside the application service for restore
   operations; the pooled URL remains the runtime `DATABASE_URL`.
7. The Azure Container App remains write-frozen and its newsletter retry loop
   remains disabled until deletion.

After the gates pass, delete in this order: Container App, Container Apps
environment, Log Analytics workspace, embedding-model storage account, Azure
PostgreSQL server, private DNS zone/link, and the retired VNet. Verify that the
managed Container Apps resource group is empty or automatically removed. Keep
the Static Web App.

## Required Railway API variables

- `DATABASE_URL`: Neon **pooled** connection URL (`-pooler` hostname).
- `DB_POOL_MODE=serverless`
- `DB_SSLMODE=require`
- `NEWSLETTER_RETRY_ENABLED=false`
- `WRITE_FREEZE_ENABLED=true` until cutover validation finishes.
- Existing application, admin, JWT, SMTP, R2, DeepSeek, YouTube, Google Search
  Console, CORS, logging, and site URL variables copied from Azure.
- Provider metadata used by Infrastructure Analytics:
  `BACKEND_PROVIDER=Railway Serverless`, `DATABASE_PROVIDER=Neon Postgres`,
  `DB_STORAGE_LIMIT_GB=0.5`, `BACKEND_MIN_REPLICAS=0`,
  `BACKEND_MAX_REPLICAS=1`.

The newsletter cron receives the same database and SMTP variables. It does not
need the API process's embedding model, analytics, or HTTP-only variables.

## Safe Railway variable export

The migration helper resolves the current Azure Container App variables and
secrets, removes Azure-only database and volume settings, and emits JSON that
Railway's Raw Editor accepts:

```bash
python "job portal backend/migration/export_railway_env.py" --service api --copy
python "job portal backend/migration/export_railway_env.py" --service newsletter --copy
```

Each command copies one complete JSON object to the macOS clipboard and reports
only the variable count. Replace `PASTE_NEON_POOLED_URL_HERE` inside Railway
before saving. The clipboard contains production secrets: never paste it into
chat or redirect it into the repository, and overwrite it after importing.

## Migration image safety

`migration/migrate-postgres.sh` accepts only a direct Neon target URL, rejects a
pooled target, and requires:

```text
ALLOW_TARGET_REPLACE=YES_I_HAVE_VERIFIED_THE_TARGET
```

The source and target URLs are secrets and must never be committed or printed.
The job is disposable and must be deleted after a verified final transfer.

For the final independent backup, run the same migration image as a one-off
Railway service with:

```text
MIGRATION_MODE=backup
BACKUP_DATABASE_URL=<Neon direct URL>
R2_BUCKET_NAME=<production backup bucket>
R2_BACKUP_PREFIX=production-backups
```

It also needs the existing R2 endpoint, access-key, and secret-key variables.
Success is reported only after `pg_restore --list`, checksum generation, upload
of both objects, and remote object-size verification all pass.

## Infrastructure cost history and payments

Infrastructure Analytics stores monthly snapshots automatically. Invoice
backfills and payments can be supplied without inventing unavailable values:

```text
INFRA_COST_HISTORY_JSON={"2026-07":{"provider_costs":{"Microsoft Azure":12.30},"paid_usd":12.30}}
INFRA_CURRENT_MONTH_PAID_USD=0
```

Historical billed cost remains visible after payment. Paid amounts reduce the
month's outstanding balance and the recorded outstanding total. The dashboard
shows only active providers: Railway, Neon, Cloudflare R2, and the retained
Azure Static Web Apps frontend.
