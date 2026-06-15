# feature/database-schema-export

## Goal

Complete database documentation per plan Section 7.

## Tasks

- [x] Generate `docs/database/schema.sql` via `scripts/db/export_schema.sh`
- [x] Add ER diagram section to `docs/database/README.md`
- [x] Ensure `migration-doc-check.yml` passes on schema changes
- [x] Align table doc names with plan (`access_grants` vs current `payments` model docs)

## Acceptance

`scripts/db/verify_docs.sh` passes with zero diff after migration.

## Completion Notes

- Added deterministic `pg_dump` schema export at `docs/database/schema.sql`.
- Expanded the ER overview and documented that access is derived from `payments`,
  `agent_runs.output_locked`, and `users.free_trial_used`.
- Fixed DB doc scripts to run from the repo root and fail on stale generated docs.
- Updated migration doc CI to run for model, script, and generated-doc changes.
- Added a real unit check for generated schema and per-table docs.
- Local validation: `pytest -q` passed with 89 tests.
- Docker validation remains pending on machines with Docker daemon available.
