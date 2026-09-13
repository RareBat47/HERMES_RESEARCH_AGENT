#!/usr/bin/env bash
# ==============================================================================
# Hermes Research Agent - Automated VM Deployment Script
# ==============================================================================
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}        🏛️  Hermes Research Agent - Automated VM Deployment      ${NC}"
echo -e "${CYAN}================================================================${NC}"

# 1. Check Root / Sudo Permissions
if [ "$EUID" -ne 0 ]; then
  SUDO="sudo"
else
  SUDO=""
fi

# 2. Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}[!] Docker not found. Installing Docker Engine...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    $SUDO sh get-docker.sh
    rm -f get-docker.sh
    $SUDO usermod -aG docker "$USER" || true
    echo -e "${GREEN}[✓] Docker installed successfully.${NC}"
else
    echo -e "${GREEN}[✓] Docker is already installed.${NC}"
fi

# 3. Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo -e "${YELLOW}[!] Docker Compose plugin not found. Installing...${NC}"
    $SUDO apt-get update && $SUDO apt-get install -y docker-compose-plugin
fi
echo -e "${GREEN}[✓] Docker Compose plugin detected: $(docker compose version)${NC}"

# 4. Check Environment File (.env)
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[!] No .env file found. Creating .env from .env.example...${NC}"
    cp .env.example .env
    echo -e "${RED}================================================================${NC}"
    echo -e "${RED}[ACTION REQUIRED] Please edit .env with your credentials:${NC}"
    echo -e "${YELLOW}  1. DISCORD_BOT_TOKEN${NC}"
    echo -e "${YELLOW}  2. LLM_API_KEY (agentrouter.org or OpenAI)${NC}"
    echo -e "${YELLOW}  3. DISCORD_RESEARCHER_1_ID and DISCORD_RESEARCHER_2_ID${NC}"
    echo -e "${RED}================================================================${NC}"
    read -p "Press [Enter] after you have configured .env to continue deployment..."
fi

# 5. Create storage directories
echo -e "${CYAN}[*] Initializing host storage directories...${NC}"
mkdir -p data/storage/papers data/storage/qdrant data/logs

# 6. Build and Launch Containers
echo -e "${CYAN}[*] Pulling images and building Hermes containers...${NC}"
$SUDO docker compose up -d --build

# 7. Health Check Verification
echo -e "${CYAN}[*] Waiting for services to initialize healthchecks (30 seconds)...${NC}"
sleep 20

echo -e "\n${CYAN}================================================================${NC}"
echo -e "${GREEN}               🚀 Hermes Stack Running Successfully!             ${NC}"
echo -e "${CYAN}================================================================${NC}"
$SUDO docker compose ps

echo -e "\n${CYAN}Service Endpoints on this VM:${NC}"
echo -e "  • ${GREEN}Hermes API & Docs:${NC}      http://localhost:8000/docs"
echo -e "  • ${GREEN}MinIO S3 Console:${NC}       http://localhost:9001"
echo -e "  • ${GREEN}Qdrant Vector DB:${NC}       http://localhost:6333/dashboard"
echo -e "  • ${GREEN}GROBID Service:${NC}         http://localhost:8070"
echo -e "\n${CYAN}Useful Operational Commands:${NC}"
echo -e "  • View live logs:            ${YELLOW}docker compose logs -f${NC}"
echo -e "  • View bot logs:             ${YELLOW}docker compose logs -f discord-bot${NC}"
echo -e "  • Restart stack:             ${YELLOW}docker compose restart${NC}"
echo -e "  • Pull updates:              ${YELLOW}./update.sh${NC}"
echo -e "${CYAN}================================================================${NC}"
