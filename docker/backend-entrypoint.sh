#!/usr/bin/env bash
set -Eeuo pipefail

echo "Applying database migrations..."
migration_file="$(find repository/migrations/versions -maxdepth 1 -type f -name '*.py' ! -name '__init__.py' -print -quit)"
if [[ -z "$migration_file" ]]; then
    echo "ERROR: no Alembic revision files found in repository/migrations/versions" >&2
    exit 1
fi
if ! uv run alembic upgrade head; then
    echo "ERROR: database migration failed; Controller API will not start" >&2
    exit 1
fi

echo "Starting Controller API..."
exec uv run uvicorn main:app --host 0.0.0.0 --port 8000
