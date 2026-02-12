# Azure VM Setup — Cloud Zone Deployment

This guide deploys the AI Employee cloud zone on an Azure Ubuntu VM with systemd for 24/7 operation.

## Prerequisites

- Azure CLI (`az`) installed and logged in
- SSH key pair (`~/.ssh/id_rsa.pub`)
- Resource group `ai-employee-rg` (or create one)
- The project repo cloned locally

## 1. Create the VM

```bash
# Create resource group (if needed)
az group create --name ai-employee-rg --location eastus

# Create Ubuntu 22.04 VM
az vm create \
  --resource-group ai-employee-rg \
  --name ai-employee-vm \
  --image Ubuntu2204 \
  --size Standard_B2s \
  --admin-username aiemployee \
  --ssh-key-values ~/.ssh/id_rsa.pub \
  --public-ip-sku Standard

# Open port 8080 for health endpoint
az vm open-port --resource-group ai-employee-rg --name ai-employee-vm --port 8080
```

Note the public IP from the output.

## 2. SSH into the VM

```bash
ssh aiemployee@<VM_PUBLIC_IP>
```

## 3. Run Bootstrap Script

```bash
# Download and run the bootstrap script
curl -fsSL https://raw.githubusercontent.com/aimanhanif321/hacthon-0/main/scripts/vm_bootstrap.sh | sudo bash
```

This installs: git, Python 3.11, Node.js 20, Claude Code CLI, uv.

## 4. Clone the Project

```bash
cd /opt/ai-employee
sudo -u aiemployee git clone https://github.com/aimanhanif321/hacthon-0.git .
```

## 5. Copy Secrets

From your local machine:

```bash
scp .env aiemployee@<VM_IP>:/opt/ai-employee/.env
scp token.json aiemployee@<VM_IP>:/opt/ai-employee/token.json
scp credentials.json aiemployee@<VM_IP>:/opt/ai-employee/credentials.json
```

## 6. Initialize Vault Git Sync

```bash
cd /opt/ai-employee/AI_Employee_Vault
git init
git remote add origin git@github.com:<your-user>/ai-employee-vault.git
git add "*.md" "**/*.md"
git commit -m "initial vault sync"
git push -u origin main
```

## 7. Install Python Dependencies

```bash
cd /opt/ai-employee
uv sync
```

## 8. Install systemd Service

```bash
sudo cp /opt/ai-employee/scripts/ai-employee-cloud.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-employee-cloud
```

## 9. Verify

```bash
# Check service status
sudo systemctl status ai-employee-cloud

# Check health endpoint
curl http://localhost:8080/health

# View logs
sudo journalctl -u ai-employee-cloud -f
```

Expected health response:
```json
{
  "status": "ok",
  "zone": "cloud",
  "timestamp": "2026-02-12T10:00:00+00:00",
  "vault_ok": true,
  "services": {
    "odoo": {"healthy": true, "last_check": "..."}
  }
}
```

## 10. Test Auto-Restart

```bash
# Kill the process — systemd should restart it in 10 seconds
sudo systemctl kill ai-employee-cloud
sleep 12
sudo systemctl status ai-employee-cloud  # should show active
```

## Cost

| Resource | SKU | Estimated Cost |
|----------|-----|---------------|
| VM | Standard_B2s (2 vCPU, 4 GB RAM) | ~$30/month |
| Disk | 30 GB managed disk | ~$2/month |
| Public IP | Standard | ~$3/month |

Stop the VM when not needed: `az vm deallocate --resource-group ai-employee-rg --name ai-employee-vm`
