# Table: `agent_runs`

Resume tailoring runs with paywall lock state.

## Columns

| Column | Type | Nullable |
|--------|------|----------|
| `id` | UUID | False |
| `user_id` | UUID | False |
| `master_resume_id` | UUID | False |
| `jd_text` | TEXT | False |
| `status` | VARCHAR(20) | False |
| `is_free_trial_run` | BOOLEAN | False |
| `output_locked` | BOOLEAN | False |
| `payment_id` | UUID | True |
| `ats_score_before` | NUMERIC(5, 2) | True |
| `ats_score_after` | NUMERIC(5, 2) | True |
| `final_output` | JSON | True |
| `preview_text` | VARCHAR(500) | True |
| `error_message` | TEXT | True |
| `total_cost_usd` | NUMERIC(10, 4) | True |
| `started_at` | DATETIME | True |
| `completed_at` | DATETIME | True |
| `created_at` | DATETIME | False |

## Indexes

- `ix_agent_runs_user_id` on (user_id)
- `ix_agent_runs_output_locked` on (output_locked)

## Foreign Keys

- `master_resume_id` → `master_resumes.id`
- `payment_id` → `payments.id`
- `user_id` → `users.id`

## Example Query

```sql
SELECT * FROM agent_runs LIMIT 10;
```
