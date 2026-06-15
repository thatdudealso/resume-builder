#!/usr/bin/env bash
set -euo pipefail
URL="${SMOKE_TEST_URL:-http://localhost:8000}"
echo "Smoke testing ${URL}"
curl -sf "${URL}/health" | grep -q '"status"'
curl -sf "${URL}/ready" | grep -q '"ready"'
echo "Smoke tests passed."
