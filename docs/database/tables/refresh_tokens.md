# Table: `refresh_tokens`

Rotating refresh tokens for JWT auth.

## Columns

| Column | Type | Nullable |
|--------|------|----------|
| `id` | UUID | False |
| `user_id` | UUID | False |
| `token_hash` | VARCHAR(64) | False |
| `expires_at` | TIMESTAMP WITH TIME ZONE | False |
| `revoked_at` | TIMESTAMP WITH TIME ZONE | True |
| `created_at` | TIMESTAMP WITH TIME ZONE | False |

## Indexes

- `ix_refresh_tokens_expires_at` on (expires_at)
- `ix_refresh_tokens_user_id` on (user_id)

## Foreign Keys

- `user_id` → `users.id`

## Example Query

```sql
SELECT * FROM refresh_tokens LIMIT 10;
```
