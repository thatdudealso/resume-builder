# Codex Context — Resume Builder

Dev-only file. **Never merge to `main`.**

## Agent workflow

- Work only on `feature/*` branches and open PRs into `develop`.
- Read `docs/dev/plans/STATUS.md` before choosing a branch.
- Update feature plan checkboxes only when explicitly asked or when finishing that branch.
- Do not commit `.env`, secrets, `.agents/`, or dev-only docs to `main`.
- Keep changes scoped to the selected feature and match existing project layout.

## Key paths

- `apps/web/main.py` — FastAPI + NiceGUI entry
- `packages/agent/graph.py` — LangGraph workflow
- `packages/core/access/service.py` — paywall logic
- `packages/db/models/` — SQLAlchemy models
- `migrations/versions/` — Alembic migrations
- `docs/database/` — generated schema docs allowed on `main`
- `docs/dev/plans/` — dev-only feature plans, never promoted to `main`

## Implementation rules

- JWT access and refresh tokens use httpOnly cookies only.
- Scope all user-data database queries by `user_id`.
- Never auto-run migrations on startup; use `scripts/migrate.sh`.
- Keep `final_output` hidden when `agent_runs.output_locked=true`.
- Unlock paid runs only through `AccessService.unlock_run()`.
- Use `payments` plus `agent_runs.output_locked` for access; there is no `access_grants` table.
- When models or migrations change, regenerate and verify `docs/database/**`.

## Commands

```bash
docker compose up --build
docker compose run --rm migrate
docker compose -f docker-compose.test.yml run --rm test
```

## Database documentation

```bash
python scripts/db/document_tables.py
bash scripts/db/export_schema.sh
bash scripts/db/verify_docs.sh
```

`scripts/db/verify_docs.sh` regenerates table docs and `schema.sql`, then fails if
`docs/database/**` has uncommitted drift.
