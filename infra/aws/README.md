# AWS Production Architecture

## Environments

| Env | Branch | ECS Service | ALB |
|-----|--------|-------------|-----|
| prod | main | resume-builder-prod | Public |
| qa | qa | resume-builder-qa | IP allowlist |
| dev | develop | resume-builder-dev | IP allowlist |

## Components

- **ECS Fargate** — single `web` task (see `task-definition.json`)
- **RDS PostgreSQL 16** — separate instance per environment
- **ElastiCache Redis 7** — rate limiting and SSE buffers
- **S3** — resumes and exports (`resume-builder-{env}`)
- **Secrets Manager** — `resume-builder/{env}/app`
- **ALB** — HTTPS, SSE idle timeout 120s
- **CloudFront** — optional for prod only

## Deploy

```bash
bash scripts/deploy/deploy-prod.sh
```

Migrate before deploy:

```bash
aws ecs run-task --cluster resume-builder-prod --task-definition resume-builder-migrate
```
