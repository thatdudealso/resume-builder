#!/usr/bin/env bash
set -euo pipefail
URL="${SMOKE_TEST_URL:-http://localhost:8000}"
echo "Smoke testing ${URL}"
curl -sf "${URL}/health" | grep -q '"status"'
curl -sf "${URL}/ready" | grep -q '"ready"'

# Public root must land in the NiceGUI app, not FastAPI's JSON 404.
ROOT_HEADERS="$(mktemp)"
ROOT_BODY="$(mktemp)"
trap 'rm -f "${ROOT_HEADERS}" "${ROOT_BODY}"' EXIT
curl -sS -D "${ROOT_HEADERS}" -o "${ROOT_BODY}" "${URL}/"
if grep -q '{"detail":"Not Found"}' "${ROOT_BODY}"; then
  echo "FAIL: ${URL}/ still returns API JSON 404" >&2
  exit 1
fi
if ! grep -qiE '^HTTP/.* (301|302|303|307|308)\b' "${ROOT_HEADERS}"; then
  echo "FAIL: ${URL}/ did not redirect into the UI" >&2
  cat "${ROOT_HEADERS}" >&2
  exit 1
fi
if ! grep -qiE '^[Ll]ocation:[[:space:]]*/app/?[[:space:]]*$' "${ROOT_HEADERS}"; then
  echo "FAIL: ${URL}/ Location is not /app/" >&2
  cat "${ROOT_HEADERS}" >&2
  exit 1
fi
UI_BODY="$(curl -sS "${URL}/app/")"
if ! printf '%s' "${UI_BODY}" | grep -qiE '<!doctype html>|Resume Builder|nicegui'; then
  echo "FAIL: ${URL}/app/ did not return ResumeBild HTML" >&2
  exit 1
fi
if printf '%s' "${UI_BODY}" | grep -q '{"detail":"Not Found"}'; then
  echo "FAIL: ${URL}/app/ returned API JSON 404" >&2
  exit 1
fi

echo "Smoke tests passed."
