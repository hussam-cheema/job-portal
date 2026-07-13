# Job Portal — Frontend (Next.js)

Navy-themed job digest UI inspired by clean issue lists (smol.ai style). Talks to the FastAPI backend.

## Setup

```bash
cd "job portal frontend"
npm install
```

`.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Run

```bash
npm run dev
```

Open http://localhost:3000

## Pages

- `/` — Latest issues (filterable job list)
- `/jobs/[id]` — Job detail, skills, apply links, study resources
