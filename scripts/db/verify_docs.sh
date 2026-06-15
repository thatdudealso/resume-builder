#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python scripts/db/document_tables.py
bash scripts/db/export_schema.sh
