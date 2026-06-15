#!/usr/bin/env bash
set -euo pipefail
ENV_NAME="${DEPLOY_ENV:-dev}"
SHA="${GITHUB_SHA:-local}"
echo "Deploying to ${ENV_NAME} with image tag ${SHA}"
docker build -t "resume-builder:${ENV_NAME}-${SHA}" .
echo "Deploy complete (local/CI stub). Configure ECS in infra/aws/ for AWS deploy."
