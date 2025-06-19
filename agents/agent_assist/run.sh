#!/bin/bash

echo "Starting from Script"

uvicorn app:app --host 0.0.0.0 --port 1238 >> ./logs/agent_assist.log 2>&1 &
if [ $? -ne 0 ]; then
    echo "Failed to start the application. Check logs for details."
    exit 1
else
    echo "Application started successfully."
fi