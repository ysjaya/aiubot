#!/bin/bash
cd "$(dirname "$0")"
python -m uvicorn main:app --host localhost --port 8000 --reload
