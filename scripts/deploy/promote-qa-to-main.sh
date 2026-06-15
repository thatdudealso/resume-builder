#!/usr/bin/env bash
# Promote qa to main by cherry-picking allowed paths only.
set -euo pipefail
ALLOWED=(
  apps packages migrations scripts/deploy scripts/db scripts/migrate.sh tests
  pyproject.toml alembic.ini Dockerfile Dockerfile.test docker-compose.yml docker-compose.test.yml
  .github docs/database README.md .env.example .gitignore infra
)
BRANCH="promote/qa-to-main-$(date +%Y%m%d%H%M%S)"
git checkout -b "$BRANCH" main
for path in "${ALLOWED[@]}"; do
  git checkout qa -- "$path" 2>/dev/null || true
done
echo "Created $BRANCH with allowed paths only. Open PR to main."
