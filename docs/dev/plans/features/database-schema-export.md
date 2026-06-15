# feature/database-schema-export

## Goal

Complete database documentation per plan Section 7.

## Tasks

- [ ] Generate `docs/database/schema.sql` via `scripts/db/export_schema.sh`
- [ ] Add ER diagram section to `docs/database/README.md`
- [ ] Ensure `migration-doc-check.yml` passes on schema changes
- [ ] Align table doc names with plan (`access_grants` vs current `payments` model docs)

## Acceptance

`scripts/db/verify_docs.sh` passes with zero diff after migration.
