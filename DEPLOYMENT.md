# 🚀 VM Deployment Guide: Hermes Research Agent

This guide outlines how to deploy the **Hermes Research Agent** on any Linux Virtual Machine (Ubuntu 22.04 / 24.04, Debian 12, AWS EC2, Hetzner, DigitalOcean, GCP Compute Engine, Oracle Cloud) directly using your GitHub repository.

---

## 📋 Recommended VM Specifications

| Component | Minimum | Recommended | Notes |
| :--- | :--- | :--- | :--- |
| **vCPU** | 2 cores | 4 cores | GROBID and Qdrant benefit from 4 cores |
| **RAM** | 4 GB | 8 GB | GROBID Java JVM runs comfortably in 8 GB |
| **Disk** | 40 GB SSD | 80 GB SSD | For PDF storage, embeddings & Docker layers |
| **OS** | Ubuntu 22.04 / 24.04 LTS | Debian 12 or Ubuntu LTS | Standard Linux kernel with Docker support |

---

## ⚡ 3-Step Quick Deployment

### Step 1: SSH into your VM and Clone Repository
```bash
# Connect to your VM
ssh user@your-vm-ip

# Clone your GitHub repository
git clone https://github.com/your-username/hermes-research-agent.git
cd hermes-research-agent
```

### Step 2: Configure Environment Credentials
```bash
# Copy template
cp .env.example .env

# Edit with nano or vim
nano .env
```
Fill in the essential variables:
```ini
# Discord Credentials (from Discord Developer Portal)
DISCORD_BOT_TOKEN=your_actual_discord_bot_token
DISCORD_GUILD_ID=your_discord_server_id

# 2-Researcher Discord User IDs (Right-click profile -> Copy User ID)
DISCORD_RESEARCHER_1_ID=123456789012345678
DISCORD_RESEARCHER_2_ID=234567890123456789

# LLM Gateway Credentials
LLM_BASE_URL=https://api.agentrouter.org/v1
LLM_API_KEY=your_agentrouter_or_openai_api_key
LLM_MODEL=gpt-4o-mini
```

### Step 3: Run the Automated Deployment Script
```bash
chmod +x deploy.sh update.sh
./deploy.sh
```

The `deploy.sh` script will:
1. Automatically verify and install Docker and Docker Compose if not already present.
2. Initialize volume storage directories.
3. Build and launch all 8 services in the background.
4. Verify service health checks.

---

## 🔄 Updating to Latest GitHub Releases

Whenever you push new code to GitHub, update your VM with a single command:
```bash
./update.sh
```
This script pulls the latest commits from `main`, rebuilds modified containers, and restarts the stack with zero downtime for database volumes.

---

## 📊 Monitoring & Useful Operations

### Check Service Status
```bash
docker compose ps
```

### Inspect Live Logs
```bash
# View all logs
docker compose logs -f

# View only the Discord bot
docker compose logs -f discord-bot

# View the background ingestion worker
docker compose logs -f worker

# View the FastAPI backend
docker compose logs -f api
```

### Restarting the System
```bash
docker compose restart
```

### Stopping the Stack
```bash
docker compose down
```

---

## 🛡️ Optional: Enable Auto-Start on System Reboot (systemd)

To make sure Hermes restarts automatically if your VM reboots:
```bash
sudo cp scripts/hermes.service /etc/systemd/system/
sudo sed -i "s|/opt/hermes-research-agent|$(pwd)|g" /etc/systemd/system/hermes.service
sudo systemctl daemon-reload
sudo systemctl enable hermes.service
```

---

## 🔒 Firewall / Security Group Configuration

If you want to access the web dashboards remotely from your browser:
- **Port 8000**: FastAPI Swagger UI (`http://your-vm-ip:8000/docs`)
- **Port 9001**: MinIO S3 Console (`http://your-vm-ip:9001`)
- **Port 6333**: Qdrant Vector Dashboard (`http://your-vm-ip:6333/dashboard`)

> **Security Recommendation**: Keep ports 5432 (PostgreSQL) and 6379 (Redis) closed to the public Internet. Only expose ports 8000 and 9001 behind an Nginx reverse proxy with HTTPS (Let's Encrypt / Certbot). The Discord bot communicates via outbound WebSocket connections to Discord's servers, so it does **not** require any open inbound ports!
