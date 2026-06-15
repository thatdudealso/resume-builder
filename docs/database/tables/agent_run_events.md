# Table: `agent_run_events`

SSE and audit events per agent run.

## Columns

| Column | Type | Nullable |
|--------|------|----------|
| `id` | INTEGER | False |
| `run_id` | UUID | False |
| `node_name` | VARCHAR(50) | False |
| `event_type` | VARCHAR(30) | False |
| `payload` | JSONB | False |
| `created_at` | TIMESTAMP WITH TIME ZONE | False |

## Indexes

- `ix_agent_run_events_run_id` on (run_id)

## Foreign Keys

- `run_id` → `agent_runs.id`

## Example Query

```sql
SELECT * FROM agent_run_events LIMIT 10;
```
