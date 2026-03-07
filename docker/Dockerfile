# =============================================================================
# Medical Search Platform - Dockerfile (Google Cloud Run ready)
# Multi-stage build for a lightweight production image
# =============================================================================

# ---------- Stage 1: Builder ----------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install system deps needed to compile Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---------- Stage 2: Runtime ----------
FROM python:3.12-slim AS runtime

# Non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

# Runtime system deps (PostgreSQL client libs only)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# App directory
WORKDIR /app

# Copy application code
COPY manage.py ./
COPY config/ ./config/
COPY search/ ./search/
COPY templates/ ./templates/
COPY static/ ./static/

# Create dirs that the app expects
RUN mkdir -p /app/logs /app/staticfiles /app/data

# Collect static files (WhiteNoise will serve them)
RUN DJANGO_SECRET_KEY=build-placeholder \
    DEBUG=false \
    ALLOWED_HOSTS=* \
    python manage.py collectstatic --noinput 2>/dev/null || true

# Copy entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Own everything by appuser
RUN chown -R appuser:appuser /app

USER appuser

# Cloud Run injects PORT; default to 8080
ENV PORT=8080
EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
