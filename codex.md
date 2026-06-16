# Codex Context — Resume Builder

Dev-only file. **Never merge to `main`.**

This is the common entrypoint for Codex and other coding agents working in this repo.
Use it before changing code, opening PRs, or updating generated documentation.

## Start Here

- Work only on `feature/*` branches, then open PRs into `develop`.
- Read `docs/dev/codex.md` for project paths, commands, and implementation rules.
- Read `docs/dev/plans/STATUS.md` before choosing or updating feature work.
- Do not commit `.env`, secrets, `.agents/`, or `docs/dev/**` to `main`.
- Keep implementation changes scoped to the selected feature branch.

## Frontend Rules

- Keep the NiceGUI app minimal, focused, and operational; do not build a marketing page.
- Use the backend API contracts in `apps/web/api/v1/**` instead of duplicating business logic.
- Login and registration must happen in the browser with `credentials: 'include'` so httpOnly cookies are stored correctly.
- Send `X-Device-Fingerprint` on auth, upload, run, billing, and export calls.
- Hide export controls until the run response includes viewable output.
- Do not display `final_output` when `agent_runs.output_locked=true`; show only `preview_text` and the paywall.
- Poll run status after Stripe or crypto payment until the webhook unlocks the run.

## Backend Coordination

- Auth cookies are set by `/api/v1/auth/register`, `/api/v1/auth/login`, and `/api/v1/auth/refresh`.
- Resume upload is `/api/v1/resumes`; only the first upload is free without confirmed payment.
- Run creation is `/api/v1/runs`; progress streams from `/api/v1/runs/{run_id}/stream`.
- Locked output is revealed only after `AccessService.unlock_run()` changes the run state.
- Exports go through `/api/v1/exports` and must respect backend access checks.

## Validation

Prefer Docker validation when Docker is available:

```bash
docker compose -f docker-compose.test.yml run --rm test
```

For local Python validation, use Python 3.12:

```bash
pytest -q
ruff check <changed-python-files>
```
