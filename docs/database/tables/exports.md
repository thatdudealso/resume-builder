# Table: `exports`

Generated export files (TXT/DOCX/PDF).

## Columns

| Column | Type | Nullable |
|--------|------|----------|
| `id` | UUID | False |
| `user_id` | UUID | False |
| `run_id` | UUID | False |
| `format` | VARCHAR(10) | False |
| `s3_key` | VARCHAR(512) | False |
| `created_at` | DATETIME | False |

## Indexes

- `ix_exports_user_id` on (user_id)

## Foreign Keys

- `run_id` → `agent_runs.id`
- `user_id` → `users.id`

## Example Query

```sql
SELECT * FROM exports LIMIT 10;
```
