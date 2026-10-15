# Contexto de construcción: raíz del repo (necesita data/ para el seed).
FROM python:3.12.7-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Capa de dependencias (cacheable): solo pyproject y lockfile
COPY apps/api/pyproject.toml apps/api/uv.lock ./apps/api/
RUN uv sync --locked --no-dev --no-install-project --project apps/api

COPY apps/api ./apps/api
COPY data ./data
RUN uv sync --locked --no-dev --project apps/api

EXPOSE 8000
CMD ["uv", "run", "--project", "apps/api", "uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000"]
