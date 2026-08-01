#!/bin/sh
set -eu
if [ "${RUN_MIGRATIONS_ON_START:-true}" = "true" ]; then
  echo "Running alembic migrations..."
  alembic upgrade head
fi
exec "$@"
