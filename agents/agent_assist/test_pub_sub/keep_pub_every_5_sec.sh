#!/bin/bash

count=0
while true; do
    echo "Publishing msg to room1 now"

    python3 manual_publisher.py

    count=$((count + 1))
    echo "Published message count: $count"
    sleep 10

done