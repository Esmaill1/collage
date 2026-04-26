#!/bin/bash
# Start the FastAPI backend in the background
echo "Starting FastAPI Backend..."
python3 api.py &
BACKEND_PID=$!

# Start the Vite React frontend
echo "Starting React Frontend..."
cd ui
npm run dev &
FRONTEND_PID=$!

echo "========================================="
echo "Saliency-Aware Collage UI is running!"
echo "Backend API: http://localhost:8000"
echo "Frontend UI: http://localhost:5173"
echo "========================================="
echo "Press Ctrl+C to stop both servers."

# Trap SIGINT to kill background processes
trap "kill $BACKEND_PID $FRONTEND_PID" SIGINT

wait $BACKEND_PID $FRONTEND_PID