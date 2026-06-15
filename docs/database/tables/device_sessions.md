# Table: `device_sessions`

Device fingerprint and IP hash per login session.

## Columns

| Column | Type | Nullable |
|--------|------|----------|
| `id` | UUID | False |
| `user_id` | UUID | False |
| `device_fingerprint` | VARCHAR(64) | False |
| `ip_hash` | VARCHAR(64) | False |
| `user_agent` | VARCHAR(512) | True |
| `first_seen_at` | DATETIME | False |
| `last_seen_at` | DATETIME | False |

## Indexes

- `ix_device_sessions_ip_hash` on (ip_hash)

## Foreign Keys

- `user_id` → `users.id`

## Example Query

```sql
SELECT * FROM device_sessions LIMIT 10;
```
