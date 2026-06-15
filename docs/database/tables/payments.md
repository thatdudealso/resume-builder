# Table: `payments`

Unified Stripe and crypto one-time payments.

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
| `metadata` | JSON | True |
| `confirmed_at` | DATETIME | True |
| `created_at` | DATETIME | False |

## Indexes

- `ix_payments_user_id` on (user_id)

## Foreign Keys

- `user_id` → `users.id`
- `run_id` → `agent_runs.id`

## Example Query

```sql
SELECT * FROM payments LIMIT 10;
```
