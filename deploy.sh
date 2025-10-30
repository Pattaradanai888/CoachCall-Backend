#!/bin/bash

# Azure VM Deployment Script for FastAPI Backend

set -e

echo "Starting FastAPI Backend Deployment"

DOCKER_IMAGE="ghcr.io/pattaradanai888/coachcall-backend:main"
CONTAINER_NAME="fastapi-backend"
APP_DIR="/opt/fastapi-backend"

if [[ $EUID -eq 0 ]]; then
    echo "Warning: Running as root"
fi

sudo mkdir -p $APP_DIR
cd $APP_DIR

if ! command -v docker &> /dev/null; then
    echo "Error: Docker not installed"
    echo "Install: curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh"
    exit 1
fi

if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose not installed"
    echo "Install: sudo apt-get update && sudo apt-get install docker-compose-plugin"
    exit 1
fi

echo "Stopping existing containers"
sudo docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true

echo "Pulling latest Docker image"
sudo docker pull $DOCKER_IMAGE

echo "Starting application"
sudo docker compose -f docker-compose.prod.yml up -d app

echo "Waiting for application startup"
sleep 10

for i in {1..12}; do
    if sudo docker compose -f docker-compose.prod.yml ps | grep -q "Up"; then
        echo "Container running"
        break
    fi
    echo "Waiting... attempt $i/12"
    sleep 5
done

echo "Running database migrations"
sudo docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head || echo "Migrations failed or already current"

if sudo docker ps | grep -q $CONTAINER_NAME; then
    echo "Application started"
    echo ""
    sudo docker ps | grep $CONTAINER_NAME
    echo ""
    sudo docker compose -f docker-compose.prod.yml logs --tail=20 app
    echo ""
    echo "Deployment completed"
    echo "Application: http://$(hostname -I | awk '{print $1}'):8000"
    echo "Health check: http://$(hostname -I | awk '{print $1}'):8000/health-check"
else
    echo "Error: Application failed to start"
    sudo docker compose -f docker-compose.prod.yml logs app
    exit 1
fi

echo ""
echo "Commands:"
echo "  Logs:    sudo docker compose -f docker-compose.prod.yml logs -f app"
echo "  Restart: sudo docker compose -f docker-compose.prod.yml restart"
echo "  Stop:    sudo docker compose -f docker-compose.prod.yml down"