FROM python:3.13.5-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    curl \
    pkg-config \
    locales \
    cmake \
    ninja-build && \
    sed -i '/it_IT.UTF-8/s/^# //g' /etc/locale.gen && \
    sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen

RUN pip install uv

COPY pyproject.toml uv.lock ./

ENV UV_HTTP_TIMEOUT=300
ENV UV_CONCURRENT_DOWNLOADS=1
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv && \
    uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"

COPY src/colf ./colf
COPY .keys ./.keys

ENV LLM_NAME=qwen2.5-1.5b-instruct-q4_k_m.gguf
ENV SERVICE_ACCOUNT_PATH=/app/.keys/sheets_mcp_service_account.json

EXPOSE 8000

CMD ["uvicorn", "colf.app:app", "--host", "0.0.0.0", "--port", "8000"]
