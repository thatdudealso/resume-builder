# Table: `crypto_webhook_events`

Idempotent crypto webhook event log.

## Columns

| Column | Type | Nullable |
|--------|------|----------|
| `id` | UUID | False |
| `provider_event_id` | VARCHAR(255) | False |
| `payment_id` | UUID | True |
| `event_type` | VARCHAR(50) | False |
| `payload` | JSONB | False |
| `processed_at` | TIMESTAMP WITH TIME ZONE | True |
| `created_at` | TIMESTAMP WITH TIME ZONE | False |

## Indexes

- _(none beyond PK)_

## Foreign Keys

- `payment_id` → `payments.id`

## Example Query

```sql
SELECT * FROM crypto_webhook_events LIMIT 10;
```
