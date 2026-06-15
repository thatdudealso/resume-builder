# Table: `master_resumes`

Uploaded master resume files and parsed text.

## Columns

| Column | Type | Nullable |
|--------|------|----------|
| `id` | UUID | False |
| `user_id` | UUID | False |
| `filename` | VARCHAR(255) | False |
| `s3_key` | VARCHAR(512) | False |
| `raw_text` | TEXT | False |
| `structured_json` | JSONB | True |
| `is_free_trial_resume` | BOOLEAN | False |
| `created_at` | TIMESTAMP WITH TIME ZONE | False |

## Indexes

- `ix_master_resumes_user_id` on (user_id)

## Foreign Keys

- `user_id` → `users.id`

## Example Query

```sql
SELECT * FROM master_resumes LIMIT 10;
```
