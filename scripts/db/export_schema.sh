#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT="${1:-docs/database/schema.sql}"
DATABASE_URL="${DATABASE_URL:-postgresql://resume:resume@localhost:5432/resume_builder}"
SYNC_URL="${DATABASE_URL/postgresql+asyncpg/postgresql}"
pg_dump "$SYNC_URL" --schema-only --no-owner --no-privileges > "$OUT" 2>/dev/null || \
  echo "-- Schema export requires running postgres" > "$OUT"
