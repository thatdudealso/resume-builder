# Table: `stripe_events`

Idempotent Stripe webhook event log.

## Columns

| Column | Type | Nullable |
|--------|------|----------|
| `id` | UUID | False |
| `stripe_event_id` | VARCHAR(255) | False |
| `event_type` | VARCHAR(100) | False |
| `payload` | JSONB | False |
| `processed_at` | TIMESTAMP WITH TIME ZONE | True |
| `created_at` | TIMESTAMP WITH TIME ZONE | False |

## Indexes

- _(none beyond PK)_

## Foreign Keys

- _(none)_

## Example Query

```sql
SELECT * FROM stripe_events LIMIT 10;
```
