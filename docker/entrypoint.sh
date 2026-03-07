#!/usr/bin/env bash
# =============================================================================
# Entrypoint for the Medical Search Platform container
# =============================================================================
set -e

echo "==> Starting Medical Search Platform..."

# Apply database migrations (safe for SQLite & PostgreSQL)
echo "==> Running migrations..."
python manage.py migrate --noinput 2>&1 || echo "Warning: migrations failed (non-fatal)"

# Collect static files if they're missing
if [ ! -d "/app/staticfiles/admin" ]; then
    echo "==> Collecting static files..."
    python manage.py collectstatic --noinput 2>&1 || true
fi

# Start gunicorn
# - Cloud Run sets PORT env (default 8080)
# - Workers: Cloud Run recommends 1 container = 1-2 workers for CPU-bound
# - Timeout: Cloud Run max request timeout is 3600s
echo "==> Starting gunicorn on port ${PORT:-8080}..."
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8080}" \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile - \
    --error-logfile - \
    --log-level info
