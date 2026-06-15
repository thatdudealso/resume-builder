#!/usr/bin/env bash
set -euo pipefail
ENV_NAME="${DEPLOY_ENV:-qa}"
SHA="${GITHUB_SHA:-local}"
echo "Deploying to ${ENV_NAME} with image tag ${SHA}"
docker build -t "resume-builder:${ENV_NAME}-${SHA}" .
bash scripts/deploy/smoke_test.sh || true
