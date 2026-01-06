FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

WORKDIR /app

# Install system dependencies for compiling Python packages (cached)
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libgeos-dev \
    libgeos-c1t64 \
    curl \
    pkg-config \
    locales && \
    sed -i '/it_IT.UTF-8/s/^# //g' /etc/locale.gen && \
    sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen

# Install uv using pip (compatible with all architectures)
RUN pip install uv

# Copy only dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
ENV UV_HTTP_TIMEOUT=300
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv && \
    uv pip install numpy && \
    uv sync --frozen

# Activate virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code (excluding files that change often)
COPY src/colf/ ./src/
COPY tests/ ./tests/
COPY .keys/ ./.keys/


EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]