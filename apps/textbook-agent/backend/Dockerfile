FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/alembic.ini ./
COPY backend/src ./src
COPY backend/contracts ./contracts
COPY backend/resources ./resources

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend/src
ENV PATH=/app/backend/.venv/bin:$PATH
ENV PORT=8000
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app/backend

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --create-home --shell /bin/bash app

COPY --from=builder /app/backend/.venv /app/backend/.venv
COPY --from=builder /app/backend/alembic.ini /app/backend/alembic.ini
COPY --from=builder /app/backend/src /app/backend/src
COPY --from=builder /app/backend/contracts /app/backend/contracts
COPY --from=builder /app/backend/resources /app/backend/resources

RUN python -m playwright install --with-deps chromium \
    && mkdir -p /app/backend/outputs/reports /app/backend/outputs/pdf \
    && chown -R app:app /app/backend /ms-playwright

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD sh -c "python -c \"import os, urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT', '8000'))\"" || exit 1

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
