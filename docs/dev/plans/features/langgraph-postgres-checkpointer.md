# feature/langgraph-postgres-checkpointer

## Goal

Persist LangGraph run state in PostgreSQL so agent runs survive container restarts (required for paid and free-trial runs).

## Tasks

- [ ] Configure `AsyncPostgresSaver` from `langgraph-checkpoint-postgres`
- [ ] Pass checkpointer into `StateGraph.compile(checkpointer=...)`
- [ ] Use `run_id` as thread id for checkpoint isolation
- [ ] Integration test: interrupt mid-run, resume, assert completion
- [ ] Document env var `DATABASE_URL` requirement in agent module

## Acceptance

Run status reaches `completed` after simulated restart during `rewrite_sections`.
