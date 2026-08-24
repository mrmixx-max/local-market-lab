# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LML_HOST=0.0.0.0 \
    LML_PORT=8322 \
    LML_DB=/data/marketlab.db

COPY pyproject.toml ./
COPY packages/ packages/
COPY apps/ apps/

RUN pip install --no-cache-dir -e ".[dev]"

VOLUME ["/data"]
EXPOSE 8322

CMD ["python", "-m", "apps.api"]
