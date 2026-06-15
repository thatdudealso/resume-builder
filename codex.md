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

## Build Rules

- Migrations are explicit; never auto-run migrations on app startup.
- All database queries that touch user data must be scoped by `user_id`.
- Auth tokens belong in httpOnly cookies only.
- The paywall must never leak `final_output` when `agent_runs.output_locked=true`.
- Stripe and crypto webhooks unlock runs through `AccessService.unlock_run()`.
- Generated database docs must be refreshed when migrations or models change.

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
