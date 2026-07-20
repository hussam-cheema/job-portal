# Job Portal — Backend (FastAPI)

REST API for Pakistani job listings with manual admin posting, YouTube QnA, CMS pages, contact form, and SEO.

## Setup

```bash
cd "job portal backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

- Root: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- UI: http://localhost:3000
- Admin login: http://localhost:3000/login (credentials from `ADMIN_USERNAME` and `ADMIN_PASSWORD`)

## Tests

```bash
source .venv/bin/activate
pytest -v
```

## Database

The application requires PostgreSQL. Configure `DATABASE_URL`, or the `POSTGRES_*` values with
`POSTGRES_HOST=postgres-db`; application startup rejects SQLite URLs. Azure PostgreSQL connections
must use TLS (`DB_SSLMODE=require` or `?sslmode=require` in `DATABASE_URL`).

On startup: creates tables, seeds admin user + sample jobs/pages when empty.

Uploads are stored in Cloudflare R2. Configure the `R2_*` variables from `.env.example`, including
a public R2 custom domain in `R2_PUBLIC_BASE_URL`.

Production can also archive filtered backend logs to the private R2 bucket.
Set `APP_ENV=production` and `R2_LOGS_ENABLED=true` (the repository CI/CD does
this automatically). Logs are stored under `production-logs/YYYY-MM-DD/`,
rotate at 100 MiB, retain the current day plus yesterday, and contain only
server lifecycle records and errors/tracebacks. Local development leaves this
disabled by default.

## Main endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Admin login |
| GET | `/api/jobs` | List/search jobs |
| GET | `/api/jobs/{id}` | Job detail + QnA |
| POST | `/api/admin/jobs` | Create job (auth) |
| PUT | `/api/admin/jobs/{id}` | Update job (auth) |
| DELETE | `/api/admin/jobs/{id}` | Delete job (auth) |
| POST | `/api/admin/jobs/{id}/fetch-qna` | Fetch YouTube QnA (auth) |
| GET/POST | `/api/pages`, `/api/admin/pages` | CMS pages |
| POST | `/api/contact` | Contact form |
| GET | `/api/admin/contact` | List messages (auth) |
| GET | `/api/admin/seo/dashboard` | SEO monitor (auth) |
| GET | `/api/admin/analytics` | Monthly site analytics (auth) |
| POST | `/api/admin/settings/logo` | Change website logo (auth) |
| GET | `/api/filters` | Filter values |
| GET | `/api/stats` | Totals |
