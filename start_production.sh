#!/bin/bash

# Build frontend
echo "Building frontend..."
cd frontend && npm run build && cd ..

# Start backend with uvicorn
echo "Starting production server on port 5000..."
python -m uvicorn main:app --host 0.0.0.0 --port 5000
