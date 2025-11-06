#!/bin/bash
# Azure App Service startup script for Python FastAPI application

echo "Starting Legal Document Automation Platform..."

# Change to the app directory
cd /home/site/wwwroot

# Start Gunicorn with Uvicorn workers
echo "Starting Gunicorn with Uvicorn workers..."
python3 -m gunicorn main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
