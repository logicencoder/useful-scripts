#!/bin/bash

echo "=========================================="
echo "  Interactive Firewall Port Manager"
echo "=========================================="
echo ""

# Ask user for port number
read -p "Enter the port number you want to open: " PORT_NUMBER

# Validate that input is a number
if ! [[ "$PORT_NUMBER" =~ ^[0-9]+$ ]]; then
    echo "ERROR: '$PORT_NUMBER' is not a valid port number!"
    echo "Please enter only numbers (e.g., 8030, 8200, 3000)"
    exit 1
fi

# Validate port range (1-65535)
if [ "$PORT_NUMBER" -lt 1 ] || [ "$PORT_NUMBER" -gt 65535 ]; then
    echo "ERROR: Port must be between 1 and 65535"
    exit 1
fi

echo ""
echo "Opening port $PORT_NUMBER..."
echo ""

# Try UFW
if command -v ufw &> /dev/null; then
    echo "Configuring UFW..."
    sudo ufw allow $PORT_NUMBER/tcp
    sudo ufw reload
    echo "UFW configured"
fi

# Try firewalld
if command -v firewall-cmd &> /dev/null; then
    echo "Configuring firewalld..."
    sudo firewall-cmd --permanent --add-port=$PORT_NUMBER/tcp
    sudo firewall-cmd --reload
    echo "firewalld configured"
fi

echo ""
echo "Port $PORT_NUMBER should now be open!"
echo "Test from another device: curl http://YOUR_IP:$PORT_NUMBER"
echo ""
