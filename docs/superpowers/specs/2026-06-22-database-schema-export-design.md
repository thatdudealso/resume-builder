# Database Schema Export — Design

**Date:** 2026-06-22
**Branch:** `feature/database-schema-export-v2` (new — old `feature/database-schema-export` is stale, predates the provider/sections refactor, and its PR #1 was closed/abandoned)
**Base:** `develop` @ `7c0a634`

## Problem

The `database-schema-export` plan item (`docs/dev/plans/features/database-schema-export.md`) was attempted once and abandoned. On current `develop`, three real gaps exist:

1. `docs/database/schema.sql` **does not exist**. It was never generated or committed.
2. `docs/database/tables/agent_runs.md` is **stale** — missing the `llm_provider` column added by migration `002_llm_provider.py`. The SQLAlchemy model (`packages/db/models/agent_run.py`) already has the column; nobody reran the generator after the migration landed.
3. `scripts/db/verify_docs.sh` **does not verify anything**. It just regenerates the docs and exits 0 regardless of whether the output differs from what's committed:
   ```bash
   python scripts/db/document_tables.py
   bash scripts/db/export_schema.sh
   ```
   `tests/unit/test_migration_docs.py` is a literal no-op: `assert readme.exists() or True`. So `migration-doc-check.yml` is wired into CI but structurally cannot catch drift.

## Scope

Postgres documentation/CI only. S3 production-hardening is an agreed separate follow-up, not part of this work.

| # | Change | File(s) |
|---|--------|---------|
| 1 | Regenerate table docs + README from current models (picks up `llm_provider`) | `docs/database/tables/*.md`, `docs/database/README.md` — run `document_tables.py`, no code changes needed |
| 2 | Generate and commit `docs/database/schema.sql` for real, via local Docker Postgres + migrations | `docs/database/schema.sql` (new file) |
| 3 | Make `verify_docs.sh` actually fail on drift: regenerate, then `git diff --exit-code` against the committed docs; also fail if `schema.sql` contains the `-- Schema export requires running postgres` placeholder | `scripts/db/verify_docs.sh` |
| 4 | Replace the placeholder test with a real one: regenerate table docs/README **in-memory** (no DB needed — `document_tables.py` only reads `Base.metadata`) and assert byte-for-byte match against the committed files | `tests/unit/test_migration_docs.py` |
| 5 | Broaden `migration-doc-check.yml`'s trigger from `migrations/**` only to also include `packages/db/models/**`, since model drift without a new migration is exactly what caused gap #2 | `.github/workflows/migration-doc-check.yml` |

## Out of scope

- S3 production hardening (lifecycle, encryption, versioning) — separate future feature.
- The currently-broken `Deploy Dev` workflow (missing `permissions: deployments: write`) — separate, queued as the next task after this one.
- Anything in `packages/agent/**` or `apps/web/**` — zero overlap by design, confirmed against all branches that touched those paths.

## Testing

- New `test_migration_docs.py` runs in the normal pytest suite, no Docker required (pure `Base.metadata` comparison) — counts toward the 85% coverage gate.
- `schema.sql` generation is verified once manually via local Docker (`docker compose -f docker-compose.test.yml up -d postgres && ... run --rm migrate`, then `pg_dump`) since `pg_dump` needs a live instance — CI already does the same dance in `migration-doc-check.yml`.

## Isolation

Done in a separate git worktree on `feature/database-schema-export-v2`, branched from `develop`, so it never touches the working directory's current branch state.
