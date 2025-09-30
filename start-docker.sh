#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "🐳 AI Code Assistant - Docker Setup"
echo "========================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ Error: .env file not found!${NC}"
    echo ""
    echo "Please create .env file:"
    echo "  1. Copy template: cp .env.example .env"
    echo "  2. Fill in your actual credentials"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ .env file found${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: Docker is not running!${NC}"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo -e "${GREEN}✅ Docker is running${NC}"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}⚠️  docker-compose not found, using 'docker compose'${NC}"
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo ""
echo -e "${BLUE}Building and starting containers...${NC}"
echo ""

# Stop existing containers
echo -e "${YELLOW}🛑 Stopping existing containers...${NC}"
$COMPOSE_CMD down

# Build and start
echo -e "${YELLOW}🔨 Building images...${NC}"
$COMPOSE_CMD build

echo -e "${YELLOW}🚀 Starting containers...${NC}"
$COMPOSE_CMD up -d

# Wait for database to be ready
echo ""
echo -e "${YELLOW}⏳ Waiting for database to be ready...${NC}"
sleep 5

# Check if containers are running
if $COMPOSE_CMD ps | grep -q "Up"; then
    echo ""
    echo "========================================"
    echo -e "${GREEN}✅ Application Started Successfully!${NC}"
    echo "========================================"
    echo ""
    echo "🌐 Access points:"
    echo "   Backend API: http://localhost:8000"
    echo "   API Docs: http://localhost:8000/docs"
    echo "   Health Check: http://localhost:8000/health"
    echo ""
    echo "📊 View logs:"
    echo "   All logs: $COMPOSE_CMD logs -f"
    echo "   Backend: $COMPOSE_CMD logs -f backend"
    echo "   Database: $COMPOSE_CMD logs -f postgres"
    echo ""
    echo "🛑 Stop application:"
    echo "   $COMPOSE_CMD down"
    echo ""
    echo "🔧 Restart application:"
    echo "   $COMPOSE_CMD restart"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Failed to start containers${NC}"
    echo ""
    echo "Check logs with: $COMPOSE_CMD logs"
    exit 1
fi
