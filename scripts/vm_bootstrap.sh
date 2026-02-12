#!/usr/bin/env bash
# vm_bootstrap.sh — One-time setup for the Azure VM (cloud zone).
#
# Run as root on a fresh Ubuntu 22.04 VM:
#   curl -fsSL https://raw.githubusercontent.com/<repo>/main/scripts/vm_bootstrap.sh | sudo bash
#
# After running this script you still need to:
#   1. SCP your .env and token.json to /opt/ai-employee/
#   2. Clone the vault repo inside AI_Employee_Vault/
#   3. Enable and start the systemd service

set -euo pipefail

APP_DIR="/opt/ai-employee"
APP_USER="aiemployee"

echo "=== [1/7] System packages ==="
apt-get update && apt-get install -y \
    git python3.11 python3.11-venv python3-pip curl wget \
    build-essential libssl-dev ca-certificates gnupg

echo "=== [2/7] Node.js 20 (for Claude Code CLI) ==="
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

echo "=== [3/7] Claude Code CLI ==="
npm install -g @anthropic-ai/claude-code || true

echo "=== [4/7] uv (Astral package manager) ==="
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.cargo/bin:$PATH"

echo "=== [5/7] Application user & directory ==="
id -u "$APP_USER" &>/dev/null || useradd -r -m -s /bin/bash "$APP_USER"
mkdir -p "$APP_DIR"
chown "$APP_USER:$APP_USER" "$APP_DIR"

echo "=== [6/7] Clone project repo ==="
if [ ! -d "$APP_DIR/.git" ]; then
    echo "Clone your project repo into $APP_DIR:"
    echo "  git clone https://github.com/aimanhanif321/hacthon-0.git $APP_DIR"
    echo "(skipping — do this manually)"
fi

echo "=== [7/7] Install Python dependencies ==="
cd "$APP_DIR"
if [ -f pyproject.toml ]; then
    uv sync
fi

echo ""
echo "=== Bootstrap complete! ==="
echo ""
echo "Next steps:"
echo "  1. Clone repo:     git clone <repo-url> $APP_DIR"
echo "  2. Copy secrets:   scp .env token.json $APP_USER@<vm-ip>:$APP_DIR/"
echo "  3. Init vault git: cd $APP_DIR/AI_Employee_Vault && git init && git remote add origin <vault-repo>"
echo "  4. Install deps:   cd $APP_DIR && uv sync"
echo "  5. Install service: cp $APP_DIR/scripts/ai-employee-cloud.service /etc/systemd/system/"
echo "  6. Enable service:  systemctl daemon-reload && systemctl enable --now ai-employee-cloud"
echo "  7. Verify:          curl http://localhost:8080/health"
