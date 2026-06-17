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
- `apps/web/ui/app.py` — single NiceGUI home page and frontend workflow
- `apps/web/ui/auth_guard.py` — backend API client for UI server calls
- `apps/web/api/v1/` — backend API contracts consumed by the UI
- `packages/agent/graph.py` — LangGraph workflow
- `packages/core/access/service.py` — paywall logic
- `packages/db/models/` — SQLAlchemy models
- `migrations/versions/` — Alembic migrations

## Frontend rules

- Keep the product screen simple and task-oriented; do not add a marketing landing page.
- The NiceGUI frontend has one user-facing page at `/app/`. Do not add
  login, registration, dashboard, account, or other product pages.
- Never add user-facing login, registration, logout, password, or account-creation
  functionality. Upload, tailoring, paywall, payment return polling, and exports
  all live on the home page.
- Set and reuse a stable `rb_device_fingerprint` cookie, then send it as
  `X-Device-Fingerprint` on API calls.
- Use backend access flags as the source of truth. Do not reveal `final_output`
  when `output_locked=true`.
- Show locked previews with the paywall, then poll run status after payment return
  until the webhook unlocks the run.
- Show export actions only after the run output is viewable; let backend export
  permissions decide allowed formats.

## Backend contracts

- Protected APIs create or reuse a private device workspace from
  `X-Device-Fingerprint` when no token is present.
- `/api/v1/auth/me` returns free-trial and upload state for the current device workspace.
- `/api/v1/resumes` uploads and lists resumes scoped to the current user.
- `/api/v1/runs` creates runs; `/api/v1/runs/{run_id}/stream` emits SSE progress.
- `/api/v1/billing/stripe/checkout` and `/api/v1/billing/crypto/invoice` create payments.
- `/api/v1/exports` creates downloads only when `AccessService.can_view_output()` passes.

## Commands

```bash
docker compose up --build
docker compose run --rm migrate
docker compose -f docker-compose.test.yml run --rm test
```
