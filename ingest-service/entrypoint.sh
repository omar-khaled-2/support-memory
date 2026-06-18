#!/bin/sh
set -e

echo "Running migrations..."
alembic upgrade head

echo "Starting application..."
exec uvicorn app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}"
