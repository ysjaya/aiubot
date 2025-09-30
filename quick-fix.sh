#!/bin/bash

# Quick Fix Script - Apply all fixes automatically
# Run this after downloading all artifacts

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================"
echo "🔧 AI Code Assistant - Quick Fix"
echo "========================================"
echo ""

# 1. Backup existing .env if it exists
if [ -f .env ]; then
    echo -e "${YELLOW}📦 Backing up existing .env...${NC}"
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo -e "${GREEN}✅ Backup created${NC}"
fi

# 2. Create .gitignore if not exists
if [ ! -f .gitignore ]; then
    echo -e "${YELLOW}📝 Creating .gitignore...${NC}"
    cat > .gitignore << 'EOF'
# Environment variables
.env
.env.local
.env.*.local

# Python
__pycache__/
*.py[cod]
*.pyc
venv/
env/
*.egg-info/

# Logs
logs/
*.log

# Database
*.db
*.sqlite

# IDE
.vscode/
.idea/
.DS_Store

# Docker
docker-compose.override.yml
EOF
    echo -e "${GREEN}✅ .gitignore created${NC}"
fi

# 3. Create .env.example if not exists
if [ ! -f .env.example ]; then
    echo -e "${YELLOW}📝 Creating .env.example...${NC}"
    cat > .env.example << 'EOF'
# AI API Keys (REGENERATE THESE!)
NVIDIA_API_KEY="your_nvidia_api_key_here"
CEREBRAS_API_KEY="your_cerebras_api_key_here"

# GitHub Integration
GITHUB_TOKEN="your_github_token_here"
GITHUB_CLIENT_ID="your_github_client_id"
GITHUB_CLIENT_SECRET="your_github_client_secret"

# Security (Generate with: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY="your_secret_key_min_64_chars"

# Database
DATABASE_URL="postgresql://username:password@host:port/database"

# Docker
POSTGRES_PASSWORD="changeme"
EOF
    echo -e "${GREEN}✅ .env.example created${NC}"
fi

# 4. Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo ""
    echo "Creating .env from template..."
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Please edit .env and fill in your credentials!${NC}"
    echo ""
fi

# 5. Create directories
echo -e "${YELLOW}📁 Creating necessary directories...${NC}"
mkdir -p logs
mkdir -p app/static
mkdir -p app/templates
mkdir -p scripts
echo -e "${GREEN}✅ Directories created${NC}"

# 6. Make scripts executable
echo -e "${YELLOW}🔑 Making scripts executable...${NC}"
chmod +x start.sh 2>/dev/null
chmod +x start-docker.sh 2>/dev/null
chmod +x quick-fix.sh 2>/dev/null
echo -e "${GREEN}✅ Scripts are executable${NC}"

# 7. Check Python version
echo ""
echo -e "${BLUE}🐍 Checking Python version...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✅ $PYTHON_VERSION${NC}"
else
    echo -e "${RED}❌ Python 3 not found!${NC}"
    echo "Please install Python 3.11+"
    exit 1
fi

# 8. Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo ""
    echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi

# 9. Generate SECRET_KEY if .env has placeholder
if grep -q "your_secret_key" .env 2>/dev/null; then
    echo ""
    echo -e "${YELLOW}🔐 Generating SECRET_KEY...${NC}"
    NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|SECRET_KEY=.*|SECRET_KEY=\"$NEW_SECRET\"|g" .env
    else
        # Linux
        sed -i "s|SECRET_KEY=.*|SECRET_KEY=\"$NEW_SECRET\"|g" .env
    fi
    echo -e "${GREEN}✅ SECRET_KEY generated${NC}"
fi

# 10. Check Docker
echo ""
echo -e "${BLUE}🐳 Checking Docker...${NC}"
if command -v docker &> /dev/null; then
    if docker info &> /dev/null; then
        echo -e "${GREEN}✅ Docker is running${NC}"
    else
        echo -e "${YELLOW}⚠️  Docker is installed but not running${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Docker not found (optional)${NC}"
fi

# 11. Summary
echo ""
echo "========================================"
echo -e "${GREEN}✅ Quick Fix Complete!${NC}"
echo "========================================"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. CRITICAL - Regenerate API Keys:"
echo "   - Cerebras: https://cerebras.ai/"
echo "   - NVIDIA: https://build.nvidia.com/"
echo "   - GitHub: https://github.com/settings/tokens"
echo ""
echo "2. Edit .env and update:"
echo "   - CEREBRAS_API_KEY"
echo "   - NVIDIA_API_KEY"
echo "   - GITHUB_TOKEN"
echo "   - DATABASE_URL"
echo ""
echo "3. Install dependencies:"
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"
echo ""
echo "4. Start application:"
echo "   ./start.sh              # Local"
echo "   ./start-docker.sh       # Docker"
echo ""
echo "5. Run tests:"
echo "   python scripts/test_system.py"
echo ""
echo "⚠️  WARNING: Your old API keys were EXPOSED!"
echo "   You MUST regenerate them before running!"
echo ""
