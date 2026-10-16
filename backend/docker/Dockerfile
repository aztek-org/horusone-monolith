# Backend Dockerfile — multi-stage build
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

# Install uv
RUN pip install uv

# Copy the packaging inputs. hatchling needs README.md and the `app` package
# (see [tool.hatch.build.targets.wheel]) to build the project wheel.
COPY pyproject.toml uv.lock README.md ./
COPY app/ ./app/

# Install the project and its runtime dependencies into a venv at /build/.venv.
# Non-editable (`--no-editable`) so the installed package is self-contained in
# the venv that gets copied into the runtime stage — an editable install would
# point back at /build, which does not exist at runtime. `uv sync` omits the
# optional `dev`/`otel` extras by default.
ENV UV_PROJECT_ENVIRONMENT=/build/.venv
RUN uv sync --no-editable

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

# Install system audio libraries required by Whisper and audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /build/.venv /app/.venv

# Copy application source
COPY app/ ./app/

# Copy alembic config and migrations
COPY alembic.ini ./
COPY alembic/ ./alembic/

# Activate the venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN useradd --create-home --shell /bin/bash horus && \
    chown -R horus:horus /app
USER horus

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
