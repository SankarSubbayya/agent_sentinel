# Sentinel gateway — FastAPI + asyncpg + google-genai.
# Used by Railway (service: gateway). Multi-stage to keep the runtime image small.

FROM python:3.12-slim AS builder

# uv is the fastest Python package manager and pyproject.toml is already the
# canonical lockfile in this project.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Cache deps in their own layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --no-dev --frozen --no-install-project

# Now install the project itself.
COPY src/ src/
COPY sql/ sql/
RUN uv sync --no-dev --frozen


FROM python:3.12-slim

WORKDIR /app

# Bring over the resolved venv from the builder stage.
COPY --from=builder /app /app

# Railway sets PORT at runtime; default to 8088 for local docker run.
ENV PORT=8088 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SENTINEL_ENV=prod

EXPOSE 8088

# Use a shell so $PORT expansion works on Railway.
CMD ["sh", "-c", "uvicorn sentinel.gateway:app --host 0.0.0.0 --port ${PORT:-8088}"]
