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
# Build and push a linux/amd64 image, then ensure the ECR repo, App Runner
# service, custom domain, Route53 CNAME records, VPC connector, and per-runtime
# Secrets Manager secrets for the existing resumebild database connection.
bash scripts/deploy/apprunner-prod.sh
```

The script never prints secret values. Credentials must already exist in Secrets Manager
or be supplied interactively into `aws secretsmanager put-secret-value` outside git.

## Runtime env (from Secrets Manager / App Runner)

The deployment script maps the app configuration described in the
[environment-variable reference](../../README.md#configure-environment-variables) to App Runner.
Store `DATABASE_URL`, `JWT_SECRET`, `OPENAI_API_KEY`, Cognito pool/client IDs, and `S3_BUCKET` in
`resumebild/production/app`; it supplies the production origin, `resumebild` S3 prefix, and
unreachable Redis endpoint needed to exercise the in-memory limiter.

The Cognito handoff validates the ResumeBild callback origin, sends the Cognito ID token in the
callback URL fragment, then exchanges it on ResumeBild for app-only HttpOnly cookies. Do not
configure a shared cookie domain or pass Cognito browser tokens between subdomains.

## Stale artifacts

`task-definition.json` describes a previous ECS+ALB plan and must not be used for this deploy.

## Outbound internet

App Runner VPC egress uses private subnets. A small `t4g.nano` NAT instance (`resumebild-nat`) provides outbound access for OpenAI/Cognito JWKS without a NAT Gateway.
