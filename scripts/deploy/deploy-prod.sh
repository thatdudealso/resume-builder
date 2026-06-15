#!/usr/bin/env bash
set -euo pipefail
ENV_NAME="${DEPLOY_ENV:-prod}"
SHA="${GITHUB_SHA:-local}"
echo "Production deploy ${SHA}"
docker build -t "resume-builder:prod-${SHA}" -t resume-builder:latest .
echo "Run ECS update-service with infra/aws/task-definition.json"
