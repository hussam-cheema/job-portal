# Production deployment guide

This guide deploys the application with the following architecture:

- **Frontend:** Azure Static Web Apps (hybrid Next.js)
- **Backend:** Azure Container Apps
- **Database:** Azure Database for PostgreSQL Flexible Server
- **Object storage:** Cloudflare R2
- **DNS and edge TLS:** Cloudflare
- **CI/CD and image registry:** GitHub Actions and GitHub Container Registry (GHCR)

The repository includes [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml). Pull requests run backend tests plus frontend lint/build checks. A successful push to `main` builds an immutable backend image, deploys a new Container Apps revision, verifies `/ready`, and then deploys the frontend. Subscriber emails are event-driven: after a new job is committed, the backend immediately emails that job to active subscribers.

## 1. Before you begin

You need:

- An active Azure subscription. The subscription shown in the screenshots must be reactivated before resources can be created.
- A GitHub repository for this project.
- A domain managed in Cloudflare.
- Azure CLI for optional command-line checks.
- Docker, Node.js 22, Python 3.12, and PostgreSQL for local testing.

Use one Azure region for the Container Apps environment and PostgreSQL. Choose a region that supports all required services and is geographically close to the majority of users. The examples below use names rather than fixed resource IDs, so choose globally unique names where Azure requires them.

Suggested names:

| Resource | Suggested name |
|---|---|
| Resource group | `job-portal-prod-rg` |
| Virtual network | `job-portal-prod-vnet` |
| Container Apps environment | `job-portal-prod-env` |
| Container App | `job-portal-api` |
| Model file share | `embedding-models` |
| PostgreSQL server | `job-portal-prod-pg-<unique>` |
| PostgreSQL database | `jobportal` |
| Static Web App | `job-portal-web` |
| R2 bucket | `job-portal-prod` |

Do not commit `.env`, Azure credentials, R2 secret keys, deployment tokens, or passwords. The root `.gitignore` already excludes local environment files.

## 2. Verify the application locally

Create local environment files:

```bash
cp "job portal backend/.env.example" "job portal backend/.env"
cp "job portal frontend/.env.example" "job portal frontend/.env.local"
```

For local development, either set `DATABASE_URL` to a local PostgreSQL instance or use the existing Docker Compose file. Set `R2_ENABLED=false` if local development does not need uploads. Use a `JWT_SECRET` of at least 32 characters and an `ADMIN_PASSWORD` between 12 and 72 characters.

Run the checks used by CI:

```bash
cd "job portal backend"
python -m pip install -r requirements.txt
pytest -q
```

```bash
cd "job portal frontend"
npm ci
npm run lint
npm run build
```

From the repository root, Docker can be checked with:

```bash
docker compose build
docker compose up
```

## 3. Create Cloudflare R2 storage

In the Cloudflare dashboard:

1. Open **R2 Object Storage** and create the `job-portal-prod` bucket.
2. Create an R2 API token restricted to this bucket with **Object Read & Write** permission.
3. Record the Access Key ID, Secret Access Key, and Cloudflare Account ID. The secret is displayed only once.
4. Connect a custom domain such as `files.example.com` to the bucket. This is the recommended production public URL.
5. Configure bucket CORS if browsers will access objects directly. Permit `GET` and `HEAD` from the production frontend origin, and only add other origins that are actually required.

Use these values later in Container Apps:

```dotenv
R2_ENABLED=true
R2_ACCOUNT_ID=<cloudflare-account-id>
R2_ACCESS_KEY_ID=<r2-access-key-id>
R2_SECRET_ACCESS_KEY=<r2-secret-access-key>
R2_BUCKET_NAME=job-portal-prod
R2_PUBLIC_BASE_URL=https://files.example.com

# Production-only backend error/lifecycle log archive in the same private R2 bucket.
APP_ENV=production
R2_LOGS_ENABLED=true
R2_LOG_PREFIX=production-logs
R2_LOG_MAX_BYTES=104857600
R2_LOG_RETENTION_DAYS=2
```

`R2_ENDPOINT` normally remains unset because the backend derives `https://<account-id>.r2.cloudflarestorage.com`. The R2 API endpoint is not the public object URL.

The API and database still expose a field named `s3_path` for compatibility with existing records and frontend code. Its value is now an R2 object key; AWS S3 is no longer used.

## 4. Create the Azure network

Private database networking avoids exposing PostgreSQL to the internet. In the Azure portal:

1. Create the production resource group.
2. Create a virtual network such as `10.0.0.0/16`.
3. Create a Container Apps infrastructure subnet, for example `10.0.0.0/23`, and delegate it to `Microsoft.App/environments`.
4. Create a PostgreSQL subnet, for example `10.0.4.0/24`, and delegate it to `Microsoft.DBforPostgreSQL/flexibleServers`.
5. Do not place other resources in either delegated subnet.

A `/23` Container Apps subnet is deliberately roomy and works with the common environment configurations. It also leaves address space for future replicas. Azure subnet requirements vary by Container Apps environment type, so confirm the portal validation before creation.

## 5. Create Azure PostgreSQL

Create an **Azure Database for PostgreSQL Flexible Server**:

1. Choose the same resource group, region, and virtual network as the backend.
2. Start with a burstable `B1ms` class when available under the subscription's free offer.
3. Choose the smallest supported storage allocation covered by the free offer (the screenshots show 32 GB).
4. Disable high availability initially to stay within budget. Enable it later when the application requires a stronger availability target.
5. Select private access, the PostgreSQL delegated subnet, and the private DNS integration offered by the portal.
6. Use locally redundant backup storage and a seven-day retention period initially.
7. Create a database named `jobportal` after the server is ready.

Construct the SQLAlchemy connection URL. URL-encode special characters in the username and password:

```text
postgresql+psycopg2://<admin-user>:<url-encoded-password>@<server>.postgres.database.azure.com:5432/jobportal?sslmode=require
```

Keep this URL for the Container App secret named `database-url`. Do not put it in GitHub repository variables or source control.

The application creates missing tables on startup. It no longer deletes an older schema automatically. Keep `RESET_DB_SCHEMA=false` in production. Use migrations or a reviewed backup/restore procedure for future schema changes.

## 6. Create the Container Apps environment and backend app

In the Azure portal:

1. Create a **Container Apps environment** in the production resource group and region.
2. Use the consumption workload profile and attach it to the Container Apps subnet created above.
3. Create a Container App named `job-portal-api` with external ingress.
4. For the initial placeholder, use `mcr.microsoft.com/azuredocs/containerapps-helloworld:latest`.
5. Set the eventual ingress target port to `8000`.
6. Keep `0.5` vCPU and `1 GiB` memory, minimum replicas `0`, and maximum replicas `2`. The application uses the official Q8 GGUF build of Qwen3-Embedding-0.6B so the existing allocation can remain unchanged.
7. Configure an HTTP liveness probe for `/health` and a readiness probe for `/ready`, both on port `8000`.

Minimum replicas of zero minimizes cost but the first request after an idle period can be slower. Set the GitHub production environment variable `BACKEND_MIN_REPLICAS=1` when consistent latency matters more than the additional compute cost. The Qwen embedding cache warms in the background, so it no longer blocks public API readiness after a cold start.

### Add persistent Qwen3 embedding model storage

When OpenAI embeddings are unavailable, the backend uses `Qwen/Qwen3-Embedding-0.6B` with cosine similarity. Its official Q8 GGUF file is about 639 MB; the official f16 file is about 1.2 GB and is not suitable for the existing 1 GiB Container App. The model must be stored on an Azure Files volume mounted at `/models`; container-local storage is ephemeral and would download it again whenever a replica is replaced.

Create the storage once before the first deployment:

1. Create or reuse a **StorageV2** Azure Storage account in the same region, using **Standard LRS**.
2. Create an Azure Files share named `embedding-models` with at least 5 GiB quota.
3. Open the **Container Apps environment** > **Volume mounts**, and add the share as an SMB Azure Files storage definition:
   - Storage name: `embeddingmodels`
   - Access mode: Read/Write
4. Open `job-portal-api` > **Revisions and replicas** > **Create new revision**.
5. Under **Volumes**, add an Azure file volume named `embedding-model-volume` using `embeddingmodels`.
6. Edit the application container and add this volume mount:
   - Volume: `embedding-model-volume`
   - Mount path: `/models`
7. Create the revision and confirm it becomes healthy.

The equivalent environment-storage registration command is:

```bash
az containerapp env storage set \
  --name <container-app-environment> \
  --resource-group <resource-group> \
  --storage-name embeddingmodels \
  --storage-type AzureFile \
  --azure-file-account-name <storage-account> \
  --azure-file-account-key <storage-account-key> \
  --azure-file-share-name embedding-models \
  --access-mode ReadWrite
```

Keep the storage account key in Azure only; do not add it to GitHub. The workflow verifies that `/models` is mounted before updating the app. During the first successful revision, the backend starts serving public requests and warms the model into the mounted Azure Files share in a background thread. Subsequent revisions reuse it immediately.

### Configure GHCR access once

GitHub Actions pushes the backend image to:

```text
ghcr.io/<github-owner>/job-portal-backend:<commit-sha>
```

The Container App needs persistent pull credentials because the workflow's `GITHUB_TOKEN` is temporary:

1. In GitHub, create a fine-grained token or classic PAT with the minimum package read permission required for GHCR. For a classic PAT this is normally `read:packages`.
2. In the Container App, open **Containers > Registry settings** and add `ghcr.io` with the GitHub username and token.
3. Keep the package private unless public image access is intentional.
4. In the GHCR package settings, grant the repository Actions access if it was not inherited automatically.

### Configure Container App secrets

Add the following secrets under the Container App's secret settings:

| Azure secret name | Value |
|---|---|
| `database-url` | Azure PostgreSQL SQLAlchemy URL |
| `jwt-secret` | Random value with at least 32 characters |
| `admin-password` | Strong password with 12-72 characters |
| `smtp-password` | SMTP/App Password for the recovery email account |
| `daily-digest-token` | Random scheduler token with at least 32 characters |
| `r2-access-key-id` | R2 Access Key ID |
| `r2-secret-access-key` | R2 Secret Access Key |

Generate a JWT secret locally, for example:

```bash
openssl rand -base64 48
```

Map these environment variables to the secrets and add the non-secret values:

```dotenv
DATABASE_URL=secretref:database-url
DB_SSLMODE=require
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=300
DB_STORAGE_LIMIT_GB=32

JWT_SECRET=secretref:jwt-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secretref:admin-password
MAX_FAILED_LOGIN_ATTEMPTS=3
ADMIN_RECOVERY_EMAIL=hussam.cheema7102@gmail.com
PASSWORD_RESET_TOKEN_TTL_MINUTES=30
PASSWORD_RESET_COOLDOWN_SECONDS=60
PASSWORD_RESET_MAX_REQUESTS_PER_IP_HOUR=5
PASSWORD_RESET_MAX_REQUESTS_PER_HOUR=10

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=hussam.cheema7102@gmail.com
SMTP_PASSWORD=secretref:smtp-password
SMTP_FROM_EMAIL=hussam.cheema7102@gmail.com
SMTP_AUTH=true
SMTP_STARTTLS=true
SMTP_USE_SSL=false
SITE_URL=https://www.example.com
SITE_NAME=PakJobs
CORS_ORIGINS=https://www.example.com,https://<static-web-app-hostname>

R2_ENABLED=true
R2_ACCOUNT_ID=<cloudflare-account-id>
R2_ACCESS_KEY_ID=secretref:r2-access-key-id
R2_SECRET_ACCESS_KEY=secretref:r2-secret-access-key
R2_BUCKET_NAME=job-portal-prod
R2_PUBLIC_BASE_URL=https://files.example.com
R2_STORAGE_LIMIT_GB=10

BACKEND_CPU_LIMIT_CORES=0.5
BACKEND_MEMORY_LIMIT_MB=1024
BACKEND_MIN_REPLICAS=0
BACKEND_MAX_REPLICAS=2
FRONTEND_PLAN=Free
FRONTEND_APP_LIMIT_MB=250
FRONTEND_BANDWIDTH_LIMIT_GB=100
INFRA_MONTHLY_BUDGET_USD=25

APP_ENV=production
R2_LOGS_ENABLED=true
R2_LOG_PREFIX=production-logs
R2_LOG_MAX_BYTES=104857600
R2_LOG_RETENTION_DAYS=2

SEED_ON_STARTUP=false
RESET_DB_SCHEMA=false
LOG_LEVEL=INFO

QWEN3_EMBEDDING_MODEL_PATH=/models/Qwen3-Embedding-0.6B-Q8_0.gguf
QWEN3_EMBEDDING_MODEL_MOUNT_PATH=/models
QWEN3_EMBEDDING_REQUIRE_PERSISTENT_STORAGE=true
QWEN3_EMBEDDING_THREADS=1
```

### Production error logs in R2

GitHub Actions applies the production logging variables above automatically on
every backend deployment. The handler reuses the existing private R2 API
credentials and bucket; no additional Cloudflare token or public URL is needed.

Objects use this layout (Pakistan Standard Time):

```text
production-logs/
  2026-07-19/
    backend-<container-instance>-0001.log
  2026-07-20/
    backend-<container-instance>-0001.log
    backend-<container-instance>-0002.log
```

- A new date folder is selected at midnight PKT.
- A new file is selected before the current file can exceed 100 MiB.
- Startup removes log objects older than yesterday, leaving only yesterday and
  the current day. Cleanup is restricted to `R2_LOG_PREFIX`, so uploaded job
  images and attachments cannot be deleted by log retention.
- Only application `ERROR`/`CRITICAL` records and the explicitly marked
  `server starting`, `server running`, and graceful `server stopped` lifecycle
  records are archived. Tracebacks produced with `logger.exception(...)` are
  stored in full. Ordinary requests, successful status messages, warnings, and
  dependency debug output remain excluded.
- Local Docker does not upload logs because `APP_ENV=production` and
  `R2_LOGS_ENABLED=true` are both required.

R2 is object storage and does not support appending. The backend therefore
maintains a private ephemeral spool and overwrites only the active log object
after each accepted event. Upload failures never terminate an API request; the
spool is retried on the next accepted event and handler diagnostics go to
standard error.

Add any YouTube or LLM API keys as Container App secrets only when those features are enabled. The local backend `.env` is not copied into the production container.

The admin **Infrastructure analytics** page collects R2 object bytes, PostgreSQL database size, backend replica CPU/RAM, and connection-pool utilization directly. `R2_STORAGE_LIMIT_GB` is a cost-control budget because R2 storage is elastic; `DB_STORAGE_LIMIT_GB` must match the PostgreSQL provisioned storage.

For live month-to-date Azure costs, enable the Container App's system-assigned managed identity, grant that identity **Cost Management Reader** on the application resource group, and set the GitHub production environment variable `AZURE_COST_MANAGEMENT_ENABLED=true`. The deployment already supplies `AZURE_SUBSCRIPTION_ID` and `AZURE_RESOURCE_GROUP`. The dashboard then groups actual costs for Container Apps, the Container Apps environment, PostgreSQL, Static Web Apps, the virtual network, load balancer, public IP, Azure Files, Log Analytics, Private DNS, and any remaining Azure resources.

If managed-identity access is not available, configure estimates directly on the Container App with `DB_MONTHLY_COST_USD`, `BACKEND_MONTHLY_COST_USD`, `FRONTEND_MONTHLY_COST_USD`, `AZURE_CONTAINER_ENV_MONTHLY_COST_USD`, `AZURE_VNET_MONTHLY_COST_USD`, `AZURE_LOAD_BALANCER_MONTHLY_COST_USD`, `AZURE_PUBLIC_IP_MONTHLY_COST_USD`, `AZURE_FILES_MONTHLY_COST_USD`, `AZURE_LOG_ANALYTICS_MONTHLY_COST_USD`, `AZURE_PRIVATE_DNS_MONTHLY_COST_USD`, `AZURE_OTHER_MONTHLY_COST_USD`, and optionally `AZURE_FORECAST_MONTHLY_COST_USD`. Unset paid services are shown as unconfigured instead of being guessed.

The first successful admin login creates the configured admin account if it does not already exist, so production does not require startup seed data.

The admin account locks after the fourth consecutive failed password attempt. Both lockout recovery and the login page's forgot-password action send a single-use reset link to `ADMIN_RECOVERY_EMAIL`. The endpoint enforces a resend cooldown plus per-IP and global hourly limits, so automation cannot flood the mailbox. The link expires after `PASSWORD_RESET_TOKEN_TTL_MINUTES` and permits choosing a new username and password without the old password. When Gmail is used for SMTP, store a Google App Password in the `smtp-password` Container App secret; never store it in GitHub or a committed `.env` file. The same SMTP account sends subscriber digests, so its App Password must remain configured after password recovery testing is complete.

To test the deployed SMTP secret and locate the exact failing stage without
printing or downloading the password, run this from Azure Cloud Shell:

```bash
az containerapp exec \
  --name job-portal-api \
  --resource-group job-portal-prod-rg \
  --command "python -m app.services.smtp_diagnostic --send"
```

The diagnostic sends one labeled message to the oldest active subscriber and
checks configuration, DNS, TCP, EHLO, TLS, authentication, envelope sender,
recipient, and final DATA acceptance. A final SMTP `250` proves Gmail accepted
responsibility for the message, but it cannot prove Inbox placement. If that
passes and the message is not visible, check the recipient's Spam and All Mail,
filters/blocked senders, and the sending account for a delayed bounce notice.

For local development, `docker compose up -d mailpit` starts a test SMTP inbox. The backend container sends recovery messages to Mailpit on port `1025`; open `http://localhost:8025` to inspect them. This avoids sending real recovery messages while testing locally.

## 7. Create Azure Static Web Apps

1. Create an **Azure Static Web App** on the Free plan.
2. Select **Other** or manual deployment as the source so Azure does not create a competing workflow. If it creates one, delete that generated workflow and retain only `.github/workflows/ci-cd.yml`.
3. After creation, copy the **deployment token** from the Static Web App's deployment settings.
4. Record the generated hostname, such as `https://<generated-name>.azurestaticapps.net`.

The frontend uses hybrid Next.js features. Check the current Azure Static Web Apps Next.js limitations before a framework upgrade or a large increase in bundle size. If the app later exceeds those limits, the frontend Dockerfile can be deployed to another Container App without changing the backend, PostgreSQL, R2, DNS, or GitHub OIDC design.

## 8. Configure Cloudflare DNS and custom domains

Use the generated Azure hostnames for the first deployment. Add custom domains after both applications are healthy:

1. In Container Apps, add `api.example.com` as a custom domain and follow Azure's TXT/CNAME validation instructions.
2. In Static Web Apps, add `www.example.com` and follow its DNS validation instructions.
3. Configure the root domain to redirect to `www.example.com`, or add it as another Static Web Apps custom domain if supported by the selected DNS setup.
4. `files.example.com` is already connected through the R2 custom-domain flow.
5. Use Cloudflare **Full (strict)** SSL mode once Azure certificates are valid.

Keep new Azure validation records DNS-only until Azure has issued and bound its certificate. You may enable the Cloudflare proxy afterward if it works with the chosen Azure custom-domain configuration. Do not cache authenticated or mutating API routes at Cloudflare.

After custom domains work, update these production values and redeploy:

```dotenv
NEXT_PUBLIC_API_URL=https://api.example.com
NEXT_PUBLIC_SITE_URL=https://www.example.com
SITE_URL=https://www.example.com
CORS_ORIGINS=https://www.example.com
```

## 9. Configure GitHub-to-Azure OIDC

The workflow uses short-lived OpenID Connect credentials and does not store an Azure client secret.

1. In Microsoft Entra ID, create an app registration/service principal for GitHub deployment.
2. Grant it **Contributor** on only the production resource group. A narrower custom role can replace Contributor later.
3. Add a federated credential for GitHub Actions.
4. Set the organization and repository to the exact GitHub owner/repository names.
5. Select **Environment** as the entity type and enter `production` because the deployment jobs use the GitHub environment named `production`.
6. Record the Azure client/application ID, tenant ID, and subscription ID.

Create a GitHub environment at **Repository Settings > Environments > production**. Optional approval rules can protect production deployments.

Add these **environment secrets** to `production`:

| Secret | Value |
|---|---|
| `AZURE_CLIENT_ID` | Entra application/client ID |
| `AZURE_TENANT_ID` | Entra tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | Static Web Apps deployment token |

Add these **environment variables** to `production`:

| Variable | Example |
|---|---|
| `AZURE_RESOURCE_GROUP` | `job-portal-prod-rg` |
| `AZURE_CONTAINER_APP_NAME` | `job-portal-api` |
| `NEXT_PUBLIC_API_URL` | `https://<container-app-fqdn>` initially |
| `NEXT_PUBLIC_SITE_URL` | `https://<static-web-app-hostname>` initially |

Do not add `DATABASE_URL`, R2 keys, the admin password, or JWT secret to these GitHub variables. They remain Azure Container App secrets.

## 10. Push the repository and run the first deployment

If the directory is not yet a Git repository:

```bash
git init
git branch -M main
git add .
git commit -m "Prepare Azure and R2 deployment"
git remote add origin git@github.com:<owner>/<repository>.git
git push -u origin main
```

The `main` push runs this sequence:

1. Backend tests.
2. Frontend lint and production build.
3. Backend image build and push to GHCR with the full commit SHA as its immutable tag.
4. Azure OIDC login and Container App revision update.
5. On the first deployment only, download the official Qwen3-Embedding-0.6B Q8 GGUF into the persistent `/models` Azure Files mount.
6. Backend `/ready` verification, including a database query and successful model-cache preparation.
7. Static Web Apps frontend build and deployment.

If the repository had to be pushed before the Azure and GitHub settings were complete, finish the configuration and run **CI and production deployment** manually from the GitHub Actions tab.

Verify the deployed services:

```bash
curl --fail https://api.example.com/health
curl --fail https://api.example.com/ready
curl --head https://www.example.com
```

Then verify:

- Public pages load and can read jobs from the API.
- Admin login works with the production credentials.
- An uploaded image or attachment receives a `https://files.example.com/...` URL.
- The object appears in the R2 bucket.
- Browser developer tools show no CORS or mixed-content failures.

## 11. Normal CI/CD operation

- Open a pull request: GitHub runs tests, lint, and build only.
- Merge to `main`: GitHub deploys the backend and then the frontend.
- A failed backend readiness check prevents the frontend deployment.
- Production secrets are maintained in Azure; changing an Azure secret creates or updates a Container Apps revision independently of a source deployment.
- Creating a new job commits the post first, then immediately sends that one job to each active subscriber. Editing an existing post does not send another alert.
- A durable delivery row is created for every active subscriber before SMTP is contacted. One failed address cannot stop the remaining recipients; failed deliveries survive container restarts and retry automatically. `SMTP_SEND_ATTEMPTS`, `NEWSLETTER_MAX_DELIVERY_ATTEMPTS`, and `NEWSLETTER_RETRY_INTERVAL_SECONDS` tune the retry policy.
- The Newsletter Subscription page shows the subscriber count, editable subject/body text, the latest per-job recipient totals, and recovery controls. SMTP failures are recorded in backend logs and do not roll back a successfully-created job.

For rollback:

- **Backend:** use Container Apps **Revisions** to direct traffic back to the last healthy revision, or rerun the workflow for a known-good commit.
- **Frontend:** revert the offending commit and push to `main`, or rerun the workflow from a known-good revision after restoring that code.
- **Database:** do not use `RESET_DB_SCHEMA`. Restore from an Azure backup to a separate server first and validate it before switching the application.

## 12. Cost controls and scaling

This design targets a low-traffic deployment under USD 25/month, but it cannot guarantee a fixed bill because Azure pricing varies by region, currency, taxes, database SKU availability, traffic, and future price changes.

During the current free period, the screenshots show applicable allowances for a burstable PostgreSQL server, 32 GB PostgreSQL storage/backup, network transfer, and selected virtual-machine services through **23 March 2027**. Confirm that the exact created meter is marked as free before relying on the allowance.

After the free period:

- Static Web Apps Free should remain the frontend baseline while its limits fit the application.
- Container Apps consumption with minimum replicas zero should be inexpensive at low traffic and scales horizontally by increasing the maximum replicas or adding HTTP/concurrency rules.
- The Qwen3 fallback adds roughly 639 MB of Azure Files storage plus file operations. The app remains at 0.5 vCPU/1 GiB while active and minimum replicas can remain zero. Monitor memory during real traffic before enabling a minimum replica or increasing concurrency.
- R2 has a free usage allowance and no egress charge to the public internet under its normal pricing model, but operations and storage above the allowance are billed.
- PostgreSQL is likely to be the largest fixed cost. Keep the smallest suitable burstable SKU, 32 GB storage, no HA, and seven-day LRS backups while traffic is small. Re-check the Azure Pricing Calculator before the free offer expires; a continuously running managed database can consume most or all of the USD 25 target in some regions.

Create an Azure Cost Management budget with alerts at USD 10, USD 20, and USD 25. Budgets notify; they do not automatically stop resources. Also create Cloudflare usage notifications where available.

Scale intentionally:

| Growth signal | First action |
|---|---|
| API cold starts become noticeable | Set Container Apps minimum replicas to 1 |
| API CPU/memory pressure | Increase per-replica resources or max replicas |
| Database connections are exhausted | Tune the backend pool conservatively before increasing PostgreSQL size |
| Database CPU/storage is sustained high | Scale PostgreSQL vertically and enable stronger backup/HA options |
| R2 traffic grows | Retain R2; increase CORS/caching controls rather than moving binary data into PostgreSQL |
| Static Web Apps hybrid limits are reached | The default homepage is cached for 15 seconds; if hybrid page latency remains high, deploy the existing frontend Docker image to Container Apps |

Avoid adding an Azure NAT Gateway, Application Gateway, dedicated load balancer, Redis, high availability, or minimum always-on replicas until there is a measured requirement; each can materially increase the baseline cost.

## 13. Troubleshooting

### Backend cannot pull the GHCR image

- Confirm `ghcr.io` registry credentials are saved on the Container App.
- Confirm the PAT has package read access and has not expired.
- Confirm the GHCR package grants access to the repository.

### `/ready` returns 503

- Check Container Apps logs for PostgreSQL connection errors.
- Confirm both resources share the virtual network and the PostgreSQL private DNS zone is linked to it.
- Confirm the URL uses the Azure server hostname and `sslmode=require`.
- Confirm the PostgreSQL subnet and Container Apps subnet are different and correctly delegated.

### Browser shows a CORS error

- Set backend `CORS_ORIGINS` to exact comma-separated HTTPS origins without paths.
- Include both the generated Static Web Apps hostname and custom domain during migration.
- Deploy a new backend revision after changing environment variables.

### Upload succeeds but the file URL fails

- Confirm `R2_PUBLIC_BASE_URL` is the public custom domain, not the R2 S3 API endpoint.
- Confirm the bucket custom domain is active and the object exists at the returned key.
- Confirm R2 bucket CORS allows the frontend origin for direct browser reads.

### GitHub OIDC login fails

- Confirm the federated credential subject uses the GitHub environment `production`.
- Confirm the client, tenant, and subscription IDs are stored in that environment.
- Confirm the service principal has permission on the correct resource group.

## Official references

- [Deploy to Azure Container Apps from GitHub Actions](https://learn.microsoft.com/azure/container-apps/github-actions)
- [Azure Container Apps virtual networks](https://learn.microsoft.com/azure/container-apps/custom-virtual-networks)
- [Azure PostgreSQL Flexible Server networking](https://learn.microsoft.com/azure/postgresql/flexible-server/concepts-networking-private)
- [GitHub Actions OIDC with Azure](https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect)
- [Next.js support in Azure Static Web Apps](https://learn.microsoft.com/azure/static-web-apps/deploy-nextjs-hybrid)
- [Cloudflare R2 S3 API compatibility](https://developers.cloudflare.com/r2/api/s3/api/)
- [Cloudflare R2 custom domains](https://developers.cloudflare.com/r2/buckets/public-buckets/)
