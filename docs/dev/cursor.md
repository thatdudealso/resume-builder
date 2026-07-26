# Cursor Agent Context — Resume Builder

Dev-only file. **Never merge to `main`.**

## Rules

- Do not edit plan files when implementing
- Do not commit `.env` or secrets
- `docs/dev/` and agent markdown never land on `main`
- Minimize scope; match existing patterns

## Payment wall

- `output_locked=true` on runs after the free trial when payments are enabled; disabled payments keep runs unlocked
- API must never leak `final_output` when locked
- Stripe/crypto webhooks unlock via `AccessService.unlock_run()`
