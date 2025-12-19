#!/bin/bash

# Initialize database
python scripts/init_db.py

# Start API server in background
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Wait for API to start
sleep 3

# Start data collector in background
python scripts/collector.py &
COLLECTOR_PID=$!

echo "Release Intelligence Platform started"
echo "API running on http://localhost:8000"
echo "API PID: $API_PID"
echo "Collector PID: $COLLECTOR_PID"
echo ""
echo "Press Ctrl+C to stop"

# Wait for interrupt
trap "kill $API_PID $COLLECTOR_PID; exit" INT TERM
wait

