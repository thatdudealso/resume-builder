# Table: `stripe_events`

Idempotent Stripe webhook event log.

## Columns

| Column | Type | Nullable |
|--------|------|----------|
| `id` | UUID | False |
| `stripe_event_id` | VARCHAR(255) | False |
| `event_type` | VARCHAR(100) | False |
| `payload` | JSON | False |
| `processed_at` | DATETIME | True |
| `created_at` | DATETIME | False |

## Indexes

- _(none beyond PK)_

## Foreign Keys

- _(none)_

## Example Query

```sql
SELECT * FROM stripe_events LIMIT 10;
```
