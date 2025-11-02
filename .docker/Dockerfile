FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv using pip (compatible with all architectures)
RUN pip install uv

# Copy only dependency files first for better caching
COPY ../pyproject.toml ../uv.lock ./

# Install dependencies first (this layer will be cached if dependencies don't change)
RUN uv sync --frozen --no-cache

# Copy application code (excluding files that change often)
COPY ../app/ ./app/
COPY ../main.py ./
# Add other specific files/directories you need

RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]