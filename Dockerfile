# syntax=docker/dockerfile:1

FROM python:3.11-slim

# Prevent python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Make python logs appear immediately
ENV PYTHONUNBUFFERED=1

# Allow imports from /app/src
ENV PYTHONPATH=/app/src

WORKDIR /app

# Install dependencies first so Docker can cache this layer
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy application source and setup scripts.
COPY src ./src
COPY scripts ./scripts
COPY data/policies ./data/policies
COPY frontend ./frontend

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app

USER appuser

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "supportcommander.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]