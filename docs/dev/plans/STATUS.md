# Resume Builder — Implementation Status

**Last updated:** 2026-06-14  
**Integration branch:** `develop`  
**Production branch:** `main` (promoted from `qa` only)

## Summary

| Metric | Status |
|--------|--------|
| Monorepo scaffold | Done |
| Auth + AccessService paywall | Done |
| LangGraph 4-node agent | Done (checkpointer pending) |
| NiceGUI dashboard | MVP done (polish pending) |
| Stripe + crypto payments | Done (webhooks + billing API) |
| Exports TXT/DOCX/PDF | Done |
| Test coverage gate | **85.42%** (89 tests) |
| CI workflows | Committed (Docker CI unverified locally) |
| AWS deploy artifacts | Skeleton only |

## Plan todos

| ID | Item | Status | Branch / notes |
|----|------|--------|----------------|
| branch-scaffold | Branches, CI guards, `docs/dev/` | **Done** | `main`, `develop`, `qa` |
| scaffold-monorepo | pyproject, Docker Compose, packages | **Done** | merged to `develop` |
| auth-access | JWT, migrations, AccessService | **Done** | |
| langgraph-agent | 4-node graph, HF, SSE | **Partial** | checkpointer → `feature/langgraph-postgres-checkpointer` |
| nicegui-ui | Upload, JD, stream, paywall, export | **Partial** | polish → `feature/nicegui-paywall-polish` |
| payments | Stripe + NOWPayments | **Done** | |
| exports-infra | Exports, S3, rate limit, headers | **Done** | |
| testing-ci | 85% gate, GHA workflows | **Partial** | Docker verify → `feature/docker-ci-verify` |
| aws-deploy | ECS, RDS, ElastiCache, ALB | **Partial** | → `feature/aws-infra-full` |

## Active feature branches (from `develop`)

Work **only** on `feature/*` branches; open PRs into `develop`.

| Branch | Scope |
|--------|--------|
| `feature/langgraph-postgres-checkpointer` | Wire `langgraph-checkpoint-postgres`; resume runs after container restart |
| `feature/nicegui-paywall-polish` | Browser cookie auth, SSE UX, post-payment polling, device fingerprint JS |
| `feature/docker-ci-verify` | Validate `docker-compose.test.yml` in CI; fix any image/test gaps |
| `feature/aws-infra-full` | Terraform/CDK or documented IaC: RDS, ElastiCache, S3, ALB, Secrets Manager |
| `feature/database-schema-export` | `docs/database/schema.sql`, ER diagram, verify_docs in CI |
| `feature/e2e-agent-tests` | Full agent E2E in Docker for `qa` promotion gate |
| `feature/github-branch-protection` | Branch protection rules doc + optional `gh` setup script |

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
