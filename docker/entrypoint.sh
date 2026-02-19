#!/usr/bin/env bash
set -e

if [ -n "$DB_HOST" ]; then
  echo "Waiting for DB ${DB_HOST}:${DB_PORT:-5432}..."
  until nc -z "$DB_HOST" "${DB_PORT:-5432}"; do
    sleep 1
  done
fi

if [ -f "alembic.ini" ] && [ "${SKIP_MIGRATIONS}" != "1" ]; then
  echo "Running alembic upgrade head..."
  alembic upgrade head || echo "Alembic failed (skip)"
fi

echo "Running seed.py..."
python app/seed.py || echo "Seed failed"

exec uvicorn app.main:app --host 0.0.0.0 --port 6123 --reload
