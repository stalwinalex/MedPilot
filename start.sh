#!/usr/bin/env bash
# MedPilot - Quick Start Script

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=============================================="
echo "  🩺 Starting MedPilot - AI Academic Companion"
echo "=============================================="

# Check if backend venv exists
if [ ! -d "backend/.venv" ]; then
    echo "Creating backend virtual environment..."
    python3.10 -m venv backend/.venv || python3 -m venv backend/.venv
    source backend/.venv/bin/activate
    pip install -r backend/requirements.txt
else
    source backend/.venv/bin/activate
fi

# Copy .env if not present in backend
if [ ! -f "backend/.env" ]; then
    echo "Initializing backend/.env from .env.example..."
    cp .env.example backend/.env
fi

# Run backend tests
echo "Running test suite to verify backend stability..."
python -m pytest backend/tests/ -q

echo ""
echo "----------------------------------------------"
echo "Starting FastAPI Backend on http://localhost:8000"
echo "Starting Vite Frontend on http://localhost:5173"
echo "----------------------------------------------"
echo ""

# Start backend in background
uvicorn app.main:app --app-dir backend --reload --port 8000 &
BACKEND_PID=$!

# Start frontend
cd frontend
npm run dev &
FRONTEND_PID=$!

# Trap cleanup
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM EXIT

wait
