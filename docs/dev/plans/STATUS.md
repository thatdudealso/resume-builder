# Resume Builder — Implementation Status

**Last updated:** 2026-06-17
**Integration branch:** `develop`
**Production branch:** `main` (promoted from `qa` only)

## Summary

| Metric | Status |
|--------|--------|
| Monorepo scaffold | Done |
| Auth + AccessService paywall | Done |
| LangGraph 4-node agent | Done |
| LangGraph Postgres checkpointer | **Done** — merged PR #2 |
| NiceGUI single-page app | **Done** — merged PR #3 |
| Stripe + crypto payments | Done (webhooks + billing API) |
| Exports TXT/DOCX/PDF | Done |
| Test coverage gate | **≥85%** (107 tests after PR #3) |
| CI workflows | Committed (Docker CI unverified locally) |
| AWS deploy artifacts | Skeleton only |

## Plan todos

| ID | Item | Status | Branch / notes |
|----|------|--------|----------------|
| branch-scaffold | Branches, CI guards, `docs/dev/` | **Done** | `main`, `develop`, `qa` |
| scaffold-monorepo | pyproject, Docker Compose, packages | **Done** | merged to `develop` |
| auth-access | JWT, migrations, AccessService | **Done** | |
| langgraph-agent | 4-node graph, HF, SSE | **Done** | |
| langgraph-checkpointer | AsyncPostgresSaver wired into graph + run_executor | **Done** | merged PR #2 |
| nicegui-ui | Single `/app/` page, device workspace, upload, SSE, paywall, post-payment polling, export gating | **Done** | merged PR #3 |
| payments | Stripe + NOWPayments | **Done** | |
| exports-infra | Exports, S3, rate limit, headers | **Done** | |
| testing-ci | 85% gate, GHA workflows | **Partial** | Docker verify → `feature/docker-ci-verify` |
| database-schema-export | `docs/database/schema.sql`, ER diagram, CI verify | **Not started** | `feature/database-schema-export` |
| e2e-agent-tests | Full agent E2E in Docker for `qa` gate | **Not started** | `feature/e2e-agent-tests` |
| github-branch-protection | Branch protection rules doc + `gh` script | **Not started** | `feature/github-branch-protection` |
| aws-deploy | ECS, RDS, ElastiCache, ALB | **Partial** | → `feature/aws-infra-full` |

## Active feature branches (from `develop`)

Work **only** on `feature/*` branches; open PRs into `develop`.

| Branch | Scope | Status |
|--------|-------|--------|
| `feature/langgraph-postgres-checkpointer` | `AsyncPostgresSaver` wired into `build_graph` / `run_agent` / `execute_run`; `get_checkpointer()` util; 6 new tests | **Merged PR #2** |
| `feature/nicegui-paywall-polish` | Single `/app/` workflow, device fingerprint auth, SSE UX, post-payment polling, export gating; 12 new tests | **Merged PR #3** |
| `feature/docker-ci-verify` | Validate `docker-compose.test.yml` in CI; fix image/test gaps | Not started |
| `feature/database-schema-export` | `docs/database/schema.sql` export, ER diagram, `verify_docs` CI check | Not started |
| `feature/e2e-agent-tests` | Full agent E2E in Docker for `qa` promotion gate | Not started |
| `feature/github-branch-protection` | Branch protection rules doc + optional `gh` setup script | Not started |
| `feature/aws-infra-full` | Terraform/CDK: RDS, ElastiCache, S3, ALB, Secrets Manager per env | Not started |

## What was completed in the last session (2026-06-17)

### `feature/nicegui-paywall-polish` → PR #3 merged
**Goal:** Production-quality NiceGUI UX — upload, tailor, pay, unlock, export in a single `/app/` page with no login/registration flow.

**Files changed:**
- `apps/web/dependencies.py` — `_request_fingerprint()` + `_get_or_create_device_user_id()` — device fingerprint creates/reuses an anonymous user keyed to `X-Device-Fingerprint` header
- `apps/web/ui/auth_guard.py` — rewrote to use `request_contextvar`, sends fingerprint header on all API calls, removed `require_auth`
- `apps/web/ui/app.py` — complete rewrite: single-page workflow, SSE progress, blur+paywall modal, post-Stripe-return polling, export gating
- `packages/integrations/stripe_client.py` — success/cancel URLs now point to `/app/?` (was `/app/dashboard?`)
- `tests/unit/apps/test_device_fingerprint.py` *(new)* — 12 tests for fingerprint extraction + device session upsert + auth paths

**Coverage:** ≥85% (107 tests) · **PR:** [#3](https://github.com/thatdudealso/resume-builder/pull/3)

## What was completed in the previous session (2026-06-16)

### `feature/langgraph-postgres-checkpointer`
**Goal:** Resume agent runs survive container restarts — keyed by `run_id` as LangGraph `thread_id`.

**Files changed:**
- `packages/agent/checkpointer.py` *(new)* — `get_checkpointer(database_url)` async context manager; converts `postgresql+asyncpg://` DSN to psycopg3 format; calls `setup()` once per run
- `packages/agent/graph.py` — `build_graph()` and `run_agent()` now accept `checkpointer: BaseCheckpointSaver | None`; config passed as `{"configurable": {"thread_id": run_id}}`
- `apps/web/services/run_executor.py` — `execute_run()` opens Postgres checkpointer for every real run
- `tests/unit/agent/test_checkpointer.py` *(new)* — DSN conversion + lifecycle mock tests
- `tests/e2e/agent_graph/test_graph.py` — E2E with `MemorySaver`; `aget_state` verifies saved output
- `tests/unit/apps/test_run_executor.py` — updated to mock `get_checkpointer`

**Coverage:** 85.94% (was 85.42%) · **Tests:** 94 (was 89) · **PR:** [#2](https://github.com/thatdudealso/resume-builder/pull/2)

## Promotion workflow

```
feature/* → develop → qa → main
```

- **Never** commit directly to `main`.
- **Never** merge `develop` → `main` in one step.
- Dev-only files (`docs/dev/**`, `*.plan.md`) live on `develop` / `qa` / `feature/*` only — blocked from `main` by `forbidden-paths-guard.yml`.

## Quick commands

```bash
git checkout develop && git pull
git checkout -b feature/my-feature
docker compose up --build
pytest --cov=packages --cov=apps --cov-fail-under=85
```

See [resume_builder_architecture.plan.md](./resume_builder_architecture.plan.md) for the full engineering plan.
See [claude.md](../claude.md) for naming conventions, data flow, and agent building context.
