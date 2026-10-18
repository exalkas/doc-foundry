FROM python:3.11-slim AS base

# Google Cloud Vision API credentials setup:
# - For production: Use Application Default Credentials (ADC) via service account
#   Mount service account JSON to /app/gcp-credentials.json or set GOOGLE_APPLICATION_CREDENTIALS
# - For local dev: Set GOOGLE_APPLICATION_CREDENTIALS env var pointing to credentials file
# See GOOGLE_VISION_SETUP.md for detailed setup instructions

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# Run a basic syntax check of all Python files
RUN find app -type f -name "*.py" -print0 | xargs -0 python -m py_compile

# Default command (can be overridden)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

ENV DB_HOST=localhost \
    DB_PORT=5432 \
    DB_NAME=docfoundry \
    DB_USER=docfoundry \
    DB_PASSWORD=docfoundry \
    ENVIRONMENT=production \
    PYTHONPATH=/app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]