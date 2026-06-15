# feature/docker-ci-verify

## Goal

Ensure `docker compose -f docker-compose.test.yml run --rm test` passes reliably in GitHub Actions.

## Tasks

- [ ] Run full Docker test suite locally and in CI
- [ ] Add MinIO or mock S3 for export tests in Docker if needed
- [ ] Pin base images and cache strategy in `feature-pr.yml`
- [ ] Document failure modes in `README.md`

## Acceptance

Green `Feature PR` workflow on a sample PR to `develop`.
