#!/usr/bin/env bash
# ==============================================================================
# Hermes Research Agent - One-Command VM Update Script
# ==============================================================================
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${CYAN}[*] Fetching latest changes from GitHub repository...${NC}"
git pull origin main

echo -e "${CYAN}[*] Rebuilding and restarting updated containers...${NC}"
docker compose up -d --build

echo -e "${GREEN}[✓] Hermes stack updated and operational!${NC}"
docker compose ps
