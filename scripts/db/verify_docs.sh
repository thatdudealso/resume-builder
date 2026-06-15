#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

python scripts/db/document_tables.py
bash scripts/db/export_schema.sh

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git diff --exit-code -- docs/database
else
  echo "Skipping stale-doc diff check outside a git worktree" >&2
fi
