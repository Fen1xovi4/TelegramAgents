#!/bin/bash
# Daily PostgreSQL backup script
# Keeps last 14 days of backups

BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
FILENAME="telegram_agents_${TIMESTAMP}.sql.gz"

echo "[$(date)] Starting backup..."

pg_dump -h postgres -U app -d telegram_agents | gzip > "${BACKUP_DIR}/${FILENAME}"

if [ $? -eq 0 ]; then
    echo "[$(date)] Backup created: ${FILENAME} ($(du -h "${BACKUP_DIR}/${FILENAME}" | cut -f1))"
else
    echo "[$(date)] ERROR: Backup failed!"
    exit 1
fi

# Remove backups older than 14 days
find "${BACKUP_DIR}" -name "telegram_agents_*.sql.gz" -mtime +14 -delete
echo "[$(date)] Cleanup done. Current backups:"
ls -lh "${BACKUP_DIR}"/telegram_agents_*.sql.gz 2>/dev/null
