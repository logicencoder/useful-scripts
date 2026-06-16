#!/bin/bash

echo "Finding all mexc_tickerz_API_subdomain_cloudflare_tunnel_version_1d.py processes..."

# Get all PIDs
PIDS=$(ps aux | grep "mexc_tickerz_API_subdomain_cloudflare_tunnel_version_1d.py" | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "No processes found!"
    exit 0
fi

echo "Found PIDs: $PIDS"
echo "Killing processes..."

# Kill all PIDs at once
sudo kill -9 $PIDS

sleep 1

# Check if any survived
REMAINING=$(ps aux | grep "mexc_tickerz_API_subdomain_cloudflare_tunnel_version_1d.py" | grep -v grep)

if [ -z "$REMAINING" ]; then
    echo "SUCCESS! All processes killed!"
else
    echo "Some processes still alive, trying harder..."
    # Get parent process and kill it
    PARENT=$(ps -o ppid= -p $(echo $PIDS | cut -d' ' -f1) | tr -d ' ')
    echo "Killing parent process: $PARENT"
    sudo kill -9 $PARENT
    
    # Nuclear option - kill the terminal
    echo "Killing terminal pts/16..."
    sudo pkill -9 -t pts/16
fi

echo "Done! Checking final status..."
ps aux | grep mexc_tickerz_API_subdomain_cloudflare_tunnel_version_1d.py | grep -v grep || echo "All dead!"
