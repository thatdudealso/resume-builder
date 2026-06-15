# feature/e2e-agent-tests

## Goal

E2E agent graph tests required for `develop` → `qa` promotion.

## Tasks

- [ ] Expand `tests/e2e/agent_graph/` with HF mocked full graph run
- [ ] Add retry loop coverage (validate → rewrite, max 2)
- [ ] Wire into `qa-promotion.yml` as required check
- [ ] Assert paywall flags on locked vs free runs

## Acceptance

QA promotion workflow fails if agent E2E regresses.
