#!/usr/bin/env bash
# Check that PR does not contain files forbidden on main.
set -euo pipefail
BASE="${1:-origin/main}"
HEAD="${2:-HEAD}"
FORBIDDEN_PATTERNS=(
  'docs/dev/'
  '.agents/'
  '.plan.md'
  '/claude.md'
  '/codex.md'
  '/cursor.md'
)
CHANGED=$(git diff --name-only "$BASE...$HEAD" 2>/dev/null || git diff --name-only "$BASE" "$HEAD")
FAILED=0
while IFS= read -r file; do
  [ -z "$file" ] && continue
  for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    if [[ "$file" == *"$pattern"* ]]; then
      echo "FORBIDDEN: $file"
      FAILED=1
    fi
  done
  if [[ "$file" == .env ]] || [[ "$file" == .env.* && "$file" != .env.example ]]; then
    echo "FORBIDDEN: $file"
    FAILED=1
  fi
done <<< "$CHANGED"
if [ "$FAILED" -eq 1 ]; then
  exit 1
fi
echo "OK: no forbidden paths"
