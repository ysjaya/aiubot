#!/bin/bash

# Build frontend
echo "Building frontend..."
cd frontend && npm run build && cd ..

# Start backend with uvicorn (use PORT from environment or default to 8080)
PORT=${PORT:-8080}
echo "Starting production server on port $PORT..."
python -m uvicorn main:app --host 0.0.0.0 --port $PORT
