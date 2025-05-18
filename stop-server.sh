#!/bin/bash

# Script to stop any running YouTube Music WebSocket servers

echo "Looking for running WebSocket server processes..."

# Find any Python processes running the youtube_music_server.py script
server_pids=$(ps aux | grep "python.*youtube_music_server\.py" | grep -v grep | awk '{print $2}')

if [ -z "$server_pids" ]; then
    echo "No running server processes found."
else
    echo "Found the following server processes:"
    ps aux | grep "python.*youtube_music_server\.py" | grep -v grep
    
    echo
    echo "Stopping processes..."
    
    # Kill each process
    for pid in $server_pids; do
        echo "Stopping process with PID $pid"
        kill $pid
    done
    
    # Wait a moment to ensure the processes have stopped
    sleep 1
    
    # Check if any processes are still running
    remaining_pids=$(ps aux | grep "python.*youtube_music_server\.py" | grep -v grep | wc -l)
    
    if [ $remaining_pids -gt 0 ]; then
        echo "Some processes are still running. Forcing termination..."
        for pid in $server_pids; do
            kill -9 $pid 2>/dev/null
        done
    fi
    
    echo "All server processes have been stopped."
fi

# Check if port 8765 is still in use
port_check=$(netstat -tuln 2>/dev/null | grep ":8765 " || ss -tuln | grep ":8765 ")

if [ -n "$port_check" ]; then
    echo
    echo "WARNING: Port 8765 is still in use by another process:"
    echo "$port_check"
    
    # Try to find the process using the port
    if command -v lsof &> /dev/null; then
        echo
        echo "Process using port 8765:"
        lsof -i :8765
    elif command -v fuser &> /dev/null; then
        echo
        echo "Process using port 8765:"
        fuser 8765/tcp -v
    fi
    
    echo
    echo "You may need to:"
    echo "1. Close the application using port 8765"
    echo "2. Edit youtube_music_server.py to use a different port"
    echo "3. Restart your computer if the issue persists"
else
    echo "Port 8765 is now available."
fi
