#!/bin/bash

# Samba Setup Script for Ubuntu Server
# This script sets up Samba to share the current user's home directory

set -e

echo "=== Ubuntu Samba Setup Script ==="
echo "This will share your home directory via Samba"
echo ""

# Get current user
CURRENT_USER=$(whoami)
HOME_DIR=$(eval echo ~$CURRENT_USER)

echo "Current user: $CURRENT_USER"
echo "Home directory: $HOME_DIR"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Error: Don't run this script as root. Run as your regular user."
    exit 1
fi

echo "Step 1: Updating package list..."
sudo apt update

echo "Step 2: Installing Samba..."
sudo apt install -y samba samba-common-bin

echo "Step 3: Backing up original Samba config..."
sudo cp /etc/samba/smb.conf /etc/samba/smb.conf.backup

echo "Step 4: Adding share configuration..."
sudo tee -a /etc/samba/smb.conf > /dev/null << EOF

[${CURRENT_USER}_home]
path = $HOME_DIR
browseable = yes
writable = yes
guest ok = no
valid users = $CURRENT_USER
create mask = 0755
directory mask = 0755
force user = $CURRENT_USER
force group = $CURRENT_USER
EOF

echo "Step 5: Creating Samba user and setting password..."
echo "You'll need to set a Samba password for user: $CURRENT_USER"
sudo smbpasswd -a $CURRENT_USER

echo "Step 6: Enabling and restarting Samba services..."
sudo systemctl enable smbd
sudo systemctl restart smbd
sudo systemctl enable nmbd
sudo systemctl restart nmbd

echo "Step 7: Configuring firewall..."
sudo ufw allow samba

echo "Step 8: Getting server IP address..."
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "=== SETUP COMPLETE ==="
echo ""
echo "Your home directory is now shared via Samba!"
echo ""
echo "To mount on Windows 11:"
echo "1. Open Command Prompt as Administrator"
echo "2. Run: net use V: \\\\$SERVER_IP\\${CURRENT_USER}_home /persistent:yes"
echo "3. Enter username: $CURRENT_USER"
echo "4. Enter the Samba password you just created"
echo ""
echo "Or use File Explorer:"
echo "Map network drive to: \\\\$SERVER_IP\\${CURRENT_USER}_home"
echo ""
echo "Share name: ${CURRENT_USER}_home"
echo "Server IP: $SERVER_IP"
echo "Username: $CURRENT_USER"
echo ""
