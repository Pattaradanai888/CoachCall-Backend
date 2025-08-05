#!/bin/bash

# Azure VM Deployment Script for FastAPI Backend
# Run this script on your Azure VM

set -e  # Exit on any error

echo "🚀 Starting FastAPI Backend Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DOCKER_IMAGE="your-dockerhub-username/fastapi-backend:latest"
CONTAINER_NAME="fastapi-backend"
APP_DIR="/opt/fastapi-backend"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root or with sudo
if [[ $EUID -eq 0 ]]; then
    print_warning "Running as root. Consider using a non-root user with sudo privileges."
fi

# Create application directory
print_status "Creating application directory..."
sudo mkdir -p $APP_DIR
cd $APP_DIR

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    echo "Run: curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    echo "Run: sudo apt-get update && sudo apt-get install docker-compose-plugin"
    exit 1
fi

# Stop existing container if running
print_status "Stopping existing containers..."
sudo docker-compose down --remove-orphans 2>/dev/null || true

# Pull latest image
print_status "Pulling latest Docker image..."
sudo docker pull $DOCKER_IMAGE

# Run database migrations
print_status "Running database migrations..."
sudo docker run --rm \
    --env-file .env \
    $DOCKER_IMAGE \
    uv run alembic upgrade head

# Start the application
print_status "Starting FastAPI application..."
sudo docker-compose up -d

# Wait for application to start
print_status "Waiting for application to start..."
sleep 30

# Check if application is running
if sudo docker ps | grep -q $CONTAINER_NAME; then
    print_status "✅ Application started successfully!"

    # Show container status
    echo ""
    print_status "Container Status:"
    sudo docker ps | grep $CONTAINER_NAME

    # Show application logs
    echo ""
    print_status "Recent application logs:"
    sudo docker-compose logs --tail=20 fastapi-app

    echo ""
    print_status "🎉 Deployment completed successfully!"
    print_status "Your FastAPI application is running on: http://$(curl -s ifconfig.me):8000"
    print_status "Health check: http://$(curl -s ifconfig.me):8000/health"

else
    print_error "❌ Application failed to start!"
    echo ""
    print_error "Container logs:"
    sudo docker-compose logs fastapi-app
    exit 1
fi

# Show useful commands
echo ""
print_status "Useful commands:"
echo "  View logs: sudo docker-compose logs -f fastapi-app"
echo "  Restart:   sudo docker-compose restart"
echo "  Stop:      sudo docker-compose down"
echo "  Update:    sudo docker pull $DOCKER_IMAGE && sudo docker-compose up -d"