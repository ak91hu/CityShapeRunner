#!/bin/sh
set -e

cleanup() {
  echo "Shutting down..."
  kill $API_PID 2>/dev/null
  kill $FRONTEND_PID 2>/dev/null
  wait
}
trap cleanup TERM INT

echo "Starting API on port 8000..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

echo "Starting frontend on port 3000..."
cd /app/frontend
node node_modules/.bin/next start --port 3000 &
FRONTEND_PID=$!

wait $FRONTEND_PID
