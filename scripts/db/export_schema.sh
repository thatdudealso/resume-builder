#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

OUT="${1:-docs/database/schema.sql}"
DATABASE_URL="${DATABASE_URL:-postgresql://resume:resume@localhost:5432/resume_builder}"
SYNC_URL="${DATABASE_URL/postgresql+asyncpg/postgresql}"
PG_DUMP_BIN="${PG_DUMP:-pg_dump}"

if ! command -v "$PG_DUMP_BIN" >/dev/null 2>&1; then
  echo "pg_dump is required to export the schema" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT")"
"$PG_DUMP_BIN" "$SYNC_URL" \
  --schema-only \
  --no-owner \
  --no-privileges \
  --restrict-key=ResumeBuilderSchema \
  --file "$OUT"
