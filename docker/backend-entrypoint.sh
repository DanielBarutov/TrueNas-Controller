#!/usr/bin/env bash
set -Eeuo pipefail

echo "Applying database migrations..."
uv run alembic upgrade head

echo "Starting Controller API..."
exec uv run uvicorn main:app --host 0.0.0.0 --port 8000
