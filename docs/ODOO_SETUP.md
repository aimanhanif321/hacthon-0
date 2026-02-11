# Odoo Setup Guide (Cloud: Azure ACI + Neon DB)

This guide covers deploying Odoo 19 on **Azure Container Instances** with a **Neon DB** (serverless PostgreSQL) backend. No local Docker or Postgres install needed.

---

## 1. Neon DB (Cloud PostgreSQL)

Neon is a serverless PostgreSQL service. The free tier (0.5 GB) is sufficient for this project.

### Setup

1. Go to https://neon.tech and sign up (GitHub login works)
2. Click **Create Project** → name it `ai-employee-odoo`
3. Choose the closest region (e.g., `East US` if using Azure East US)
4. Once created, copy the connection string:
   ```
   postgresql://neondb_owner:password123@ep-cool-name-123456.eastus2.azure.neon.tech/neondb?sslmode=require
   ```
5. Add to your `.env`:
   ```
   NEON_DATABASE_URL=postgresql://neondb_owner:password123@ep-cool-name-123456.eastus2.azure.neon.tech/neondb?sslmode=require
   ```

### Why Neon instead of local Postgres?

- Zero local disk usage
- Free tier is sufficient
- Always-on, no Docker needed
- Odoo connects to it the same way it connects to any Postgres instance

---

## 2. Odoo on Azure Container Instances

Azure Container Instances (ACI) runs a Docker container in the cloud without managing a VM. You pay per-second of usage and can stop it when not in use.

### Prerequisites

- Azure account (free tier or pay-as-you-go)
- Azure CLI: `winget install Microsoft.AzureCLI` (or https://aka.ms/installazurecliwindows)

### Step-by-step

**1. Login to Azure CLI:**
```bash
az login
```

**2. Create a Resource Group** (a folder for your Azure resources):
```bash
az group create --name ai-employee-rg --location eastus
```

**3. Deploy Odoo container** pointing to Neon DB:
```bash
az container create \
  --resource-group ai-employee-rg \
  --name odoo-server \
  --image odoo:19.0 \
  --ports 8069 \
  --cpu 1 \
  --memory 1.5 \
  --environment-variables \
    HOST=ep-cool-name-123456.eastus2.azure.neon.tech \
    USER=neondb_owner \
    PASSWORD=your_neon_password \
  --ip-address Public \
  --dns-name-label ai-employee-odoo
```
Replace `HOST`, `USER`, `PASSWORD` with your actual Neon DB values from step 1.

**4. Get Odoo public URL:**
```bash
az container show --resource-group ai-employee-rg --name odoo-server --query ipAddress.fqdn -o tsv
```
This gives you something like: `ai-employee-odoo.eastus.azurecontainer.io`

Your Odoo URL is: `http://ai-employee-odoo.eastus.azurecontainer.io:8069`

**5. First-time Odoo setup:**
- Open the Odoo URL in your browser
- Create database: name = `ai-employee`, email = your email, password = choose one
- Odoo will initialize tables in your Neon DB automatically
- Install the **Accounting** module from the Apps menu

**6. Add to `.env`:**
```env
ODOO_URL=http://ai-employee-odoo.eastus.azurecontainer.io:8069
ODOO_DB=ai-employee
ODOO_USERNAME=admin
ODOO_PASSWORD=your_odoo_password
```

### Stopping / Starting (save costs)

```bash
# Stop (pauses billing):
az container stop --resource-group ai-employee-rg --name odoo-server

# Start again:
az container start --resource-group ai-employee-rg --name odoo-server
```

---

## 3. Verify

**Test connectivity from the AI Employee:**
```bash
uv run python -c "from mcp_servers.odoo_server import test_connection; test_connection()"
```

**Test MCP server tools:**
```bash
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | uv run python -m mcp_servers.odoo_server
```

**Check Neon dashboard:**
Login to https://console.neon.tech — your database should show Odoo's tables after first-run setup.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `SSL required` error | Neon requires SSL — ensure Odoo connects with `sslmode=require` in the connection string |
| `Authentication failed` | Verify ODOO_USERNAME/PASSWORD match what you set during first-time Odoo setup |
| Container won't start | Check logs: `az container logs --resource-group ai-employee-rg --name odoo-server` |
| Slow first connection | ACI cold-starts take ~30s. Use `az container start` to warm it up |
| Can't reach Odoo URL | Verify the container is running: `az container show --resource-group ai-employee-rg --name odoo-server --query instanceView.state` |
