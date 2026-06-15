# Table: `crypto_payments`

On-chain payment details for crypto unlocks.

## Columns

| Column | Type | Nullable |
|--------|------|----------|
| `id` | UUID | False |
| `payment_id` | UUID | False |
| `pay_currency` | VARCHAR(20) | False |
| `pay_amount` | NUMERIC(20, 8) | False |
| `pay_address` | VARCHAR(255) | True |
| `tx_hash` | VARCHAR(255) | True |
| `confirmations` | INTEGER | False |
| `webhook_payload` | JSONB | True |

## Indexes

- _(none beyond PK)_

## Foreign Keys

- `payment_id` → `payments.id`

## Example Query

```sql
SELECT * FROM crypto_payments LIMIT 10;
```
