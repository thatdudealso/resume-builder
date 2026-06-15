# feature/github-branch-protection

## Goal

Enforce branch governance on GitHub matching Section 0 of the architecture plan.

## Tasks

- [ ] Document required protection rules for `main`, `qa`, `develop`
- [ ] Optional script using `gh api` to apply rules (requires admin)
- [ ] Require `forbidden-paths-guard` on PRs to `main`
- [ ] Require 85% coverage + migration doc check on PRs to `develop`

## Acceptance

Direct push to `main` rejected; PR to `main` with `docs/dev/` change fails CI.
