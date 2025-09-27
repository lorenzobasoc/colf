FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv using pip (compatible with all architectures)
RUN pip install uv

# Copy dependency files from parent directory
COPY ../pyproject.toml ../uv.lock ./

RUN uv sync --frozen --no-cache

# Copy application code from parent directory
COPY ../ .

RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]