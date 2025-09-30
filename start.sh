#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "🚀 AI Code Assistant Startup"
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

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${GREEN}✅ Activating virtual environment${NC}"
source venv/bin/activate

# Install/update dependencies
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Check database connection
echo -e "${YELLOW}🔍 Checking database connection...${NC}"
python -c "
from app.core.config import settings
from sqlalchemy import create_engine, text
try:
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Cannot connect to database. Please check DATABASE_URL in .env${NC}"
    exit 1
fi

echo ""
echo "========================================"
echo "🎯 Starting Application..."
echo "========================================"
echo ""
echo "Backend will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
echo ""
echo "Press CTRL+C to stop"
echo ""

# Start the application
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
