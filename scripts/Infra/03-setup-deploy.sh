#!/bin/bash
###############################################################################
# Script 03 : Setup git-based deploy for MCP Manager
#
# A executer DANS le container LXC (en tant que root).
# Configure le deploy par git pull + rebuild au lieu de tar+scp.
#
# Usage :
#   ssh root@192.168.10.99 "bash -s" < scripts/Infra/03-setup-deploy.sh
#
# Ensuite pour deployer :
#   ssh root@192.168.10.99 "/root/deploy-mcp.sh"
###############################################################################
set -eu

PROJECT_DIR="/root/mcp-manager"
DEPLOY_SCRIPT="/root/deploy-mcp.sh"
REPO_URL="${1:-https://github.com/gaelgael5/mcp-manager.git}"
BRANCH="${2:-master}"

echo "==========================================="
echo "  Setup Git Deploy — MCP Manager"
echo "==========================================="
echo ""

# ── 1. Install git si absent ────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
    echo "[1/3] Installing git..."
    apt-get update -qq && apt-get install -y -qq git
else
    echo "[1/3] Git already installed"
fi

# ── 2. Clone ou configure le repo ───────────────────────────────────────────
echo "[2/3] Configuring repository..."

if [ -d "${PROJECT_DIR}/.git" ]; then
    echo "  -> Git repo already exists, updating remote"
    cd "${PROJECT_DIR}"
    git remote set-url origin "${REPO_URL}" 2>/dev/null || git remote add origin "${REPO_URL}"
    git fetch origin
    echo "  -> Remote updated"
else
    echo "  -> Initializing git in existing project"
    cd "${PROJECT_DIR}"
    git init
    git remote add origin "${REPO_URL}"
    git fetch origin
    git checkout -f "${BRANCH}"
    echo "  -> Repo initialized on branch ${BRANCH}"
fi

# ── 3. Creer le script de deploy ────────────────────────────────────────────
echo "[3/3] Creating deploy script..."

cat > "${DEPLOY_SCRIPT}" << DEPLOYEOF
#!/bin/bash
# MCP Manager — Git Deploy
# Usage: /root/deploy-mcp.sh
set -eu

cd ${PROJECT_DIR}
LOG="/root/deploy.log"

echo "\$(date '+%Y-%m-%d %H:%M:%S') === DEPLOY START ===" >> \$LOG

# Pull latest
echo "\$(date +%H:%M:%S) — Git pull..." >> \$LOG
git fetch origin ${BRANCH}
git reset --hard origin/${BRANCH} >> \$LOG 2>&1
echo "\$(date +%H:%M:%S) — \$(git log --oneline -1)" >> \$LOG

# Rebuild & restart
echo "\$(date +%H:%M:%S) — Rebuilding..." >> \$LOG
docker compose up -d --build mcp-backend mcp-frontend >> \$LOG 2>&1

# Verify
echo "\$(date +%H:%M:%S) — Verifying..." >> \$LOG
sleep 5
if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "\$(date +%H:%M:%S) — Deploy OK" >> \$LOG
    echo "Deploy OK"
else
    echo "\$(date +%H:%M:%S) — Deploy FAILED — backend not healthy" >> \$LOG
    echo "Deploy FAILED"
    exit 1
fi

echo "\$(date '+%Y-%m-%d %H:%M:%S') === DEPLOY DONE ===" >> \$LOG
DEPLOYEOF

chmod +x "${DEPLOY_SCRIPT}"

echo ""
echo "==========================================="
echo "  Git Deploy configured"
echo ""
echo "  Repo   : ${REPO_URL}"
echo "  Branch : ${BRANCH}"
echo "  Script : ${DEPLOY_SCRIPT}"
echo "  Log    : /root/deploy.log"
echo ""
echo "  Pour deployer :"
echo "    ssh root@192.168.10.99 /root/deploy-mcp.sh"
echo ""
echo "  Ou depuis Windows :"
echo "    ssh -i ~/.ssh/id_shellia root@192.168.10.99 /root/deploy-mcp.sh"
echo "==========================================="
