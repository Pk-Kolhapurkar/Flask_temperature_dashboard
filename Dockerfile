# Dockerfile for ThermoScan AI
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PORT 8000

# Install system dependencies including git
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    git \
    libsqlite3-dev && \
    rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY static ./static
COPY templates ./templates

# Initialize database - FIXED FUNCTION NAME
RUN python -c "from app import init_sqlite_db; init_sqlite_db()"

# Expose the application port
EXPOSE $PORT

# Start the application with Gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
