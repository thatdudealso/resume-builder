# Resume Builder

AI-powered resume tailoring — upload a master resume, paste a job description, get an ATS-optimized rewrite with no hallucinated facts.

## Stack

- Python 3.12, FastAPI, NiceGUI, LangGraph
- PostgreSQL, Redis, S3
- Stripe + NOWPayments (crypto) pay-per-run unlock

## Local development

```bash
cp .env.example .env
docker compose up --build
```

App: http://localhost:8000/app  
API: http://localhost:8000/api/v1  
Health: http://localhost:8000/health

## Migrations

Migrations are **never** auto-run on startup:

```bash
docker compose run --rm migrate
```

## Tests

```bash
docker compose -f docker-compose.test.yml run --rm test
```

## Branch workflow

- `develop` — active development (private deploy)
- `qa` — pre-production (private deploy)
- `main` — production only (public app URL)

**GitHub:** private repo; engineering plan and status live on `develop` under `docs/dev/plans/`.

```bash
git checkout develop
# Read docs/dev/plans/STATUS.md for current status and feature branches
```

Feature work: branch from `develop` as `feature/<name>`, open PR → `develop`.
