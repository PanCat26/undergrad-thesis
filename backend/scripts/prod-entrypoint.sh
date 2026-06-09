#!/usr/bin/env sh
set -e

echo "Applying database migrations..."
alembic upgrade head

# --proxy-headers + --forwarded-allow-ips lets uvicorn trust Caddy's X-Forwarded-For/Proto,
# so the real client IP (used by the guest-issuance throttle) and HTTPS scheme are correct.
echo "Starting API server (prod)..."
exec uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 \
    --proxy-headers --forwarded-allow-ips="*" \
    --workers "${UVICORN_WORKERS:-2}"
