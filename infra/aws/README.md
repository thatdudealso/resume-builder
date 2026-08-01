# AWS App Runner production layout (replaces the stale ECS task-definition path)

## Target

- Domain: `https://resumebild.5432wire.com`
- Compute: AWS App Runner (NiceGUI WebSocket + in-process run queues)
- Auth: Cognito redirect handoff via `https://5432wire.com/login?return_url=...`
- DB: shared RDS database `resumebild`
- Object storage: existing 5432wire bucket with `resumebild/` prefix
- Redis: not required (in-memory rate-limit fallback)
- Secrets: AWS Secrets Manager (`resumebild/production/app`)

## Provisioning

```bash
# Create ECR repo, Secrets Manager secret, App Runner service, custom domain,
# Route53 alias, VPC connector, and resumebild database.
bash scripts/deploy/apprunner-prod.sh
```

The script never prints secret values. Credentials must already exist in Secrets Manager
or be supplied interactively into `aws secretsmanager put-secret-value` outside git.

## Runtime env (from Secrets Manager / App Runner)

| Key | Notes |
|-----|-------|
| `ENV` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://.../resumebild` |
| `JWT_SECRET` | app-only session cookies (not Cognito) |
| `OPENAI_API_KEY` | from managed secret |
| `COGNITO_USER_POOL_ID` / `COGNITO_APP_CLIENT_ID` / `COGNITO_REGION` | shared 5432wire pool |
| `PUBLIC_BASE_URL` | `https://resumebild.5432wire.com` |
| `AUTH_LOGIN_URL` | `https://5432wire.com/login` |
| `AUTH_RETURN_ALLOWLIST` | `https://resumebild.5432wire.com` |
| `S3_BUCKET` / `S3_PREFIX` / `S3_REGION` | shared bucket + `resumebild` prefix |
| `CORS_ORIGINS` | `https://resumebild.5432wire.com` |
| `REDIS_URL` | optional; leave unset / unreachable for in-memory limiter |

## Stale artifacts

`task-definition.json` describes a previous ECS+ALB plan and must not be used for this deploy.

## Outbound internet

App Runner VPC egress uses private subnets. A small `t4g.nano` NAT instance (`resumebild-nat`) provides outbound access for OpenAI/Cognito JWKS without a NAT Gateway.
