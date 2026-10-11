#!/usr/bin/with-contenv bashio
set -e

echo "Starting Travel Assistant..."

# Ensure data directory exists
mkdir -p /data

# Start the FastAPI application
cd /app
python3 -m uvicorn main:app --host 0.0.0.0 --port 8099 --log-level info
