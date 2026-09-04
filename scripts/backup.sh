#!/usr/bin/env bash
set -euo pipefail

# RepoTrajectory Automated PostgreSQL Backup Script
# Retention Policy: 7 daily backups, 4 weekly backups

BACKUP_DIR="${BACKUP_DIR:-/backups}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-github_analytics}"
POSTGRES_DB="${POSTGRES_DB:-github_analytics}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
DAY_OF_WEEK=$(date -u +"%u") # 1=Monday, 7=Sunday

mkdir -p "${BACKUP_DIR}/daily"
mkdir -p "${BACKUP_DIR}/weekly"

BACKUP_FILE="${BACKUP_DIR}/daily/repotrajectory_${TIMESTAMP}.sql.gz"

echo "[$(date -u)] Starting database backup of ${POSTGRES_DB} on ${POSTGRES_HOST}:${POSTGRES_PORT}..."

# Execute compressed pg_dump
PGPASSWORD="${POSTGRES_PASSWORD:-github_analytics}" pg_dump \
  -h "${POSTGRES_HOST}" \
  -p "${POSTGRES_PORT}" \
  -U "${POSTGRES_USER}" \
  -d "${POSTGRES_DB}" \
  -Fc | gzip -c > "${BACKUP_FILE}"

FILESIZE=$(stat -c%s "${BACKUP_FILE}" 2>/dev/null || stat -f%z "${BACKUP_FILE}" 2>/dev/null || echo "unknown")
echo "[$(date -u)] Daily backup completed: ${BACKUP_FILE} (${FILESIZE} bytes)"

# On Sundays, copy to weekly archive
if [ "${DAY_OF_WEEK}" -eq 7 ]; then
  WEEKLY_FILE="${BACKUP_DIR}/weekly/repotrajectory_${TIMESTAMP}.sql.gz"
  cp "${BACKUP_FILE}" "${WEEKLY_FILE}"
  echo "[$(date -u)] Weekly archive created: ${WEEKLY_FILE}"
fi

# Prune daily backups older than 7 days
echo "[$(date -u)] Enforcing 7-day retention on daily backups..."
find "${BACKUP_DIR}/daily" -name "repotrajectory_*.sql.gz" -type f -mtime +7 -delete || true

# Prune weekly backups older than 28 days (4 weeks)
echo "[$(date -u)] Enforcing 4-week retention on weekly backups..."
find "${BACKUP_DIR}/weekly" -name "repotrajectory_*.sql.gz" -type f -mtime +28 -delete || true

echo "[$(date -u)] Backup and retention lifecycle successfully completed."
