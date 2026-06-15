# Table: `users`

Application users with free trial tracking.

## Columns

| Column | Type | Nullable |
|--------|------|----------|
| `id` | UUID | False |
| `email` | VARCHAR(255) | False |
| `password_hash` | VARCHAR(255) | False |
| `is_active` | BOOLEAN | False |
| `free_trial_used` | BOOLEAN | False |
| `created_at` | TIMESTAMP WITH TIME ZONE | False |
| `updated_at` | TIMESTAMP WITH TIME ZONE | False |

## Indexes

- _(none beyond PK)_

## Foreign Keys

- _(none)_

## Example Query

```sql
SELECT * FROM users LIMIT 10;
```
