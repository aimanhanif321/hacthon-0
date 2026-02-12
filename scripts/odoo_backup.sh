#!/usr/bin/env bash
# odoo_backup.sh — Nightly pg_dump backup of Odoo's Neon DB.
#
# Add to crontab on the Azure VM:
#   0 2 * * * /opt/ai-employee/scripts/odoo_backup.sh >> /opt/ai-employee/logs/backup.log 2>&1
#
# Requires: NEON_DATABASE_URL in .env (or exported)

set -euo pipefail

BACKUP_DIR="/opt/ai-employee/backups"
RETENTION_DAYS=7
DATE=$(date +%Y-%m-%d)
BACKUP_FILE="${BACKUP_DIR}/odoo_backup_${DATE}.dump"

# Load env vars
if [ -f /opt/ai-employee/.env ]; then
    set -a
    source /opt/ai-employee/.env
    set +a
fi

if [ -z "${NEON_DATABASE_URL:-}" ]; then
    echo "ERROR: NEON_DATABASE_URL not set"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Starting Odoo backup..."

# pg_dump using the Neon connection string
pg_dump "$NEON_DATABASE_URL" \
    --format=custom \
    --no-owner \
    --no-privileges \
    --file="$BACKUP_FILE"

FILESIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat --printf="%s" "$BACKUP_FILE" 2>/dev/null || echo "unknown")
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Backup complete: $BACKUP_FILE ($FILESIZE bytes)"

# Cleanup old backups
echo "Cleaning up backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "odoo_backup_*.dump" -mtime +${RETENTION_DAYS} -delete -print

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) Backup job finished"
