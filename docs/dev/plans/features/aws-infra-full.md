# feature/aws-infra-full

## Goal

Deployable AWS infrastructure for dev, qa, and prod environments.

## Tasks

- [ ] RDS PostgreSQL 16 per environment
- [ ] ElastiCache Redis 7
- [ ] S3 buckets `resume-builder-{env}`
- [ ] ALB + HTTPS (IP allowlist for dev/qa)
- [ ] Secrets Manager paths `resume-builder/{env}/app`
- [ ] ECS services wired to deploy scripts
- [ ] Smoke test + rollback validated against QA

## Acceptance

`scripts/deploy/deploy-qa.sh` succeeds against real AWS account (documented placeholders replaced).
