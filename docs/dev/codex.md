# Codex Context — Resume Builder

Dev-only file. **Never merge to `main`.**

## Key paths

- `apps/web/main.py` — FastAPI + NiceGUI entry
- `packages/agent/graph.py` — LangGraph workflow
- `packages/core/access/service.py` — paywall logic
- `packages/db/models/` — SQLAlchemy models
- `migrations/versions/` — Alembic migrations

## Commands

```bash
docker compose up --build
docker compose run --rm migrate
docker compose -f docker-compose.test.yml run --rm test
```
