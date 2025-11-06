#!/bin/bash
# Azure App Service startup script for Python FastAPI application

echo "Starting Legal Document Automation Platform..."

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create database tables
echo "Creating database tables..."
python3 -c "from database.db_client import DatabaseClient; DatabaseClient.create_tables()"

# Start Gunicorn with Uvicorn workers
echo "Starting Gunicorn with Uvicorn workers..."
gunicorn main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
