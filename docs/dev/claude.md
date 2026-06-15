# Claude Code Context — Resume Builder

Dev-only file. **Never merge to `main`.**

## Product

Pay-per-run resume tailoring. Free trial: 1 resume + 1 JD + visible output. Second run locks output until $9.99 payment.

## Architecture

- Monorepo: `apps/web` (FastAPI + NiceGUI), `packages/*`
- LangGraph 4-node agent: prepare_inputs → rewrite → validate → format
- HF Inference API for rewrite + validate only

## Conventions

- JWT in httpOnly cookies only
- All DB queries scoped by user_id
- Alembic migrations explicit, never on startup
- 85% test coverage gate
