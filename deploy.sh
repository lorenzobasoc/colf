#!/bin/bash

# Deployment script for Colf Django app to Raspberry Pi
# Usage: ./deploy.sh

set -e

# Configuration
RASPBERRY_PI_HOST="kali-raspberrypi"
RASPBERRY_PI_USER="kali"
PROJECT_NAME="colf"
REMOTE_PATH="/home/kali/apps/colf"

echo "🚀 Starting deployment to Raspberry Pi..."

# Check if we can reach the Raspberry Pi
echo "📡 Checking connection to Raspberry Pi..."
if ! ping -c 1 $RASPBERRY_PI_HOST > /dev/null 2>&1; then
    echo "❌ Cannot reach $RASPBERRY_PI_HOST. Make sure your VPN is connected."
    exit 1
fi

echo "✅ Raspberry Pi is reachable"

# Create remote directory if it doesn't exist
echo "📁 Setting up remote directory..."
ssh $RASPBERRY_PI_USER@$RASPBERRY_PI_HOST "mkdir -p $REMOTE_PATH"

# Copy project files to Raspberry Pi
echo "📋 Copying project files..."
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' \
    ./ $RASPBERRY_PI_USER@$RASPBERRY_PI_HOST:$REMOTE_PATH/

# Deploy on Raspberry Pi
echo "🐳 Building and deploying Docker container..."
ssh $RASPBERRY_PI_USER@$RASPBERRY_PI_HOST << EOF
    cd $REMOTE_PATH
    
    # Stop existing container if running
    docker-compose down || true
    
    # Build new image
    docker-compose build
    
    # Start the application
    docker-compose up -d
    
    # Show status
    docker-compose ps
    
    echo "🎉 Deployment completed!"
    echo "📱 App should be available at: http://kali-raspberrypi:8000"
    echo "🔧 Portainer: https://kali-raspberrypi:9443"
EOF

echo "✅ Deployment script completed successfully!"
echo "🌐 Your Django app should now be running on: http://kali-raspberrypi:8000"