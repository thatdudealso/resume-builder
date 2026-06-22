#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
alembic upgrade head
python scripts/db/setup_langgraph_checkpoints.py
echo "Migrations applied."
