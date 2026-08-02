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

# Browser: automatic Cognito auth must not land on /app/api/v1/... NiceGUI 404.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! command -v npm >/dev/null 2>&1; then
  echo "FAIL: npm is required for browser auth smoke" >&2
  exit 1
fi
echo "==> Browser auth smoke against ${URL}"
BROWSER_SMOKE_DIR="$(mktemp -d)"
cleanup_browser_smoke() {
  rm -f "${ROOT_HEADERS}" "${ROOT_BODY}"
  rm -rf "${BROWSER_SMOKE_DIR}"
}
trap cleanup_browser_smoke EXIT
# ESM resolves packages from the script directory; run inside a temp install.
cp "${ROOT_DIR}/scripts/deploy/browser_auth_smoke.mjs" "${BROWSER_SMOKE_DIR}/browser_auth_smoke.mjs"
npm install --prefix "${BROWSER_SMOKE_DIR}" --silent playwright@1.62.0
"${BROWSER_SMOKE_DIR}/node_modules/.bin/playwright" install chromium >/dev/null
(
  cd "${BROWSER_SMOKE_DIR}"
  SMOKE_TEST_URL="${URL}" node ./browser_auth_smoke.mjs
)

echo "Smoke tests passed."
