#!/bin/bash

# Deployment script for Colf FastAPI app to Raspberry Pi
# Usage: ./deploy.sh

set -e

# Configuration
RASPBERRY_PI_HOST="kali-raspberrypi"
RASPBERRY_PI_USER="kali"
PROJECT_NAME="colf"
REMOTE_PATH="/home/kali/apps/colf"

echo "Starting deployment to Raspberry Pi..."

# Check if we can reach the Raspberry Pi
echo "Checking connection to Raspberry Pi..."
if ! ping -c 1 $RASPBERRY_PI_HOST > /dev/null 2>&1; then
    echo "Cannot reach $RASPBERRY_PI_HOST. Make sure your VPN is connected."
    exit 1
fi

echo "Raspberry Pi is reachable"

# Create remote directory if it doesn't exist
echo "Setting up remote directory..."
ssh $RASPBERRY_PI_USER@$RASPBERRY_PI_HOST "mkdir -p $REMOTE_PATH"

# Copy project files to Raspberry Pi
echo "Copying project files..."
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' \
    ../ $RASPBERRY_PI_USER@$RASPBERRY_PI_HOST:$REMOTE_PATH/

# Deploy on Raspberry Pi
echo "Building and deploying Docker container..."
ssh $RASPBERRY_PI_USER@$RASPBERRY_PI_HOST << EOF
    cd $REMOTE_PATH
    
    echo "Current directory: \$(pwd)"
    echo "Files in directory:"
    ls -la
    
    echo "Checking .docker directory:"
    ls -la .docker/
    
    cd .docker
    
    echo "Current directory: \$(pwd)"
    echo "Docker compose file content:"
    cat docker-compose.yml
    
    # Stop existing container if running
    echo "Stopping existing containers..."
    docker-compose down || true
    
    # Remove existing images to force rebuild
    echo "Removing existing images..."
    docker-compose down --rmi all || true
    
    # Build new image
    echo "Building new image..."
    docker-compose build --no-cache
    
    # Start the application
    echo "Starting application..."
    docker-compose up -d
    
    # Show status
    docker-compose ps
    
    # Show docker containers
    echo "Docker containers running:"
    docker ps -a
    
    # Show docker networks
    echo "Docker networks:"
    docker network ls
    
    # Test the health endpoint
    echo "Testing health endpoint..."
    sleep 5
    curl -f http://localhost:8000/api/health || echo "Health check failed, but container might still be starting..."
    
    # Show logs if something went wrong
    echo "Container logs:"
    docker-compose logs --tail=20
    
    echo "Deployment completed!"
    echo "App available at: http://kali-raspberrypi:9901"
    echo "API docs: http://kali-raspberrypi:9901/docs"
    echo "Portainer: https://kali-raspberrypi:9443"
EOF

echo "Deployment script completed successfully!"
echo "Your FastAPI app should now be running on: http://kali-raspberrypi:9901"