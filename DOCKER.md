# Docker (backend + frontend)

Uses the existing Postgres container `postgres-db` on the shared network `jobportal-net`.
Uploads use Cloudflare R2 credentials from `job portal backend/.env`.

## Start

```bash
cd "job portal"

# Share network with existing Postgres
docker network create jobportal-net 2>/dev/null || true
docker network connect jobportal-net postgres-db 2>/dev/null || true

docker compose up -d --build
```

- Backend API: http://localhost:8000  
- Frontend UI: http://localhost:3000  
- Docs: http://localhost:8000/docs  

## Stop

```bash
docker compose down
```

## Logs

```bash
docker compose logs -f backend
docker compose logs -f frontend
```
