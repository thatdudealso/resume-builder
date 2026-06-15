# Table: `payments`

Unified Stripe and crypto payment records that unlock paid runs.

## Columns

| Column | Type | Nullable |
|--------|------|----------|
| `id` | UUID | False |
| `user_id` | UUID | False |
| `run_id` | UUID | True |
| `provider` | VARCHAR(20) | False |
| `provider_payment_id` | VARCHAR(255) | False |
| `idempotency_key` | VARCHAR(255) | False |
| `amount_usd` | NUMERIC(10, 2) | False |
| `currency` | VARCHAR(10) | False |
| `status` | VARCHAR(20) | False |
| `unlocks_uploads` | BOOLEAN | False |
| `metadata` | JSONB | True |
| `confirmed_at` | TIMESTAMP WITH TIME ZONE | True |
| `created_at` | TIMESTAMP WITH TIME ZONE | False |

## Indexes

- `ix_payments_user_id` on (user_id)

## Foreign Keys

- `run_id` → `agent_runs.id`
- `user_id` → `users.id`

## Example Query

```sql
SELECT * FROM payments LIMIT 10;
```
