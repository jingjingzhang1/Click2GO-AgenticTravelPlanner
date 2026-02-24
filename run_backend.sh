#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Click2GO – Backend Startup Script
#
# Usage:
#   ./run_backend.sh            (development, port 8000, auto-reload)
#   ./run_backend.sh --prod     (production-style, no reload)
# ─────────────────────────────────────────────────────────────────────────────
set -e

# Source environment variables if .env exists
if [ -f .env ]; then
    echo "Loading environment from .env"
    export $(grep -v '^#' .env | xargs)
fi

# Create outputs directory for PDF / map artefacts
mkdir -p outputs

if [[ "$1" == "--prod" ]]; then
    echo "Starting Click2GO in PRODUCTION mode..."
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2
else
    echo "Starting Click2GO in DEVELOPMENT mode (auto-reload)..."
    echo "API docs: http://127.0.0.1:8000/docs"
    echo "Press Ctrl+C to stop."
    uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
fi
