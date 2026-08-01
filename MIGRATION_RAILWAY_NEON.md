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
   PostgreSQL server intact while production is monitored. Delete them only
   after explicit approval. Azure Static Web Apps and the other requested Azure
   services stay in place.

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

## Migration image safety

`migration/migrate-postgres.sh` accepts only a direct Neon target URL, rejects a
pooled target, and requires:

```text
ALLOW_TARGET_REPLACE=YES_I_HAVE_VERIFIED_THE_TARGET
```

The source and target URLs are secrets and must never be committed or printed.
The job is disposable and must be deleted after a verified final transfer.
