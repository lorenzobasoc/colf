FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files first for better caching
COPY pyproject.toml ./

# Install dependencies with cache mounts
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/app/.venv \
    uv sync --no-dev

# Copy application code
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

CMD ["uv", "run", "python", "run.py"]