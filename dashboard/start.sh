#!/bin/bash
# Start the T20 Cricket Analytics Dashboard

# Resolve the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🏏 Starting T20 Analytics Dashboard..."

# Kill anything already on these ports
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null

# Backend
cd "$SCRIPT_DIR/backend"
uvicorn main:app --port 8000 &
BACKEND_PID=$!
echo "✅ Backend running on http://localhost:8000 (PID $BACKEND_PID)"

# Frontend — serve from the frontend folder
cd "$SCRIPT_DIR/frontend"
python3 -m http.server 3000 &
FRONTEND_PID=$!
echo "✅ Frontend running on http://localhost:3000 (PID $FRONTEND_PID)"

echo ""
echo "👉 Open: http://localhost:3000"
echo "   Press Ctrl+C to stop both servers"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" INT
wait
