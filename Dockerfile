# Multi-stage build for smaller final image
FROM python:3.11.13-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy uv configuration files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-cache --no-dev

# Production stage
FROM python:3.11.13-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Create proper Python symlinks in venv
RUN ln -sf /usr/local/bin/python3.11 /app/.venv/bin/python && \
    ln -sf /usr/local/bin/python3.11 /app/.venv/bin/python3 && \
    ln -sf /usr/local/bin/python3.11 /app/.venv/bin/python3.11

# Copy application code
COPY . .

# Remove unnecessary files
RUN rm -rf .git .github htmlcov tests scripts *.md .env.dev.template .env.prod.template

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV ENVIRONMENT=production
ENV DEBUG=false

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health-check || exit 1

# Use python from PATH
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]