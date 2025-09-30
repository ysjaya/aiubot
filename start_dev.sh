#!/bin/bash

# Start backend on port 8000
echo "Starting backend on port 8000..."
python -m uvicorn main:app --host localhost --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend on port 5000
echo "Starting frontend on port 5000..."
cd frontend && npm run dev

# Cleanup on exit
trap "kill $BACKEND_PID 2>/dev/null" EXIT
