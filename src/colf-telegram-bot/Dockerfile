FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

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

CMD ["uv", "run", "python", "run.py"]