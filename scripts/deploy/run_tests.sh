#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
ruff check apps packages tests
mypy apps packages
pytest --cov=packages --cov=apps --cov-report=term-missing --cov-fail-under=85 "$@"
