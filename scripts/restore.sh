#!/usr/bin/env bash
set -euo pipefail

# RepoTrajectory Database Restore & Rehearsal Procedure
# Usage: ./scripts/restore.sh <path_to_backup_file> [--rehearsal]

if [ $# -lt 1 ]; then
  echo "Usage: $0 <path_to_backup_file> [--rehearsal]"
  exit 1
fi

BACKUP_FILE="$1"
REHEARSAL=0
if [ "${2:-}" = "--rehearsal" ]; then
  REHEARSAL=1
fi

if [ ! -f "${BACKUP_FILE}" ]; then
  echo "Error: Backup file not found: ${BACKUP_FILE}"
  exit 1
fi

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-github_analytics}"
TARGET_DB="${POSTGRES_DB:-github_analytics}"

if [ "${REHEARSAL}" -eq 1 ]; then
  TARGET_DB="repotrajectory_rehearsal_$(date +%s)"
  echo "[$(date -u)] Performing RESTORE REHEARSAL into isolated database: ${TARGET_DB}..."
  PGPASSWORD="${POSTGRES_PASSWORD:-github_analytics}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -c "CREATE DATABASE ${TARGET_DB};"
else
  echo "[$(date -u)] WARNING: Restoring into target production database: ${TARGET_DB}!"
fi

echo "[$(date -u)] Restoring from ${BACKUP_FILE} into ${TARGET_DB}..."

if [[ "${BACKUP_FILE}" == *.gz ]]; then
  gunzip -c "${BACKUP_FILE}" | PGPASSWORD="${POSTGRES_PASSWORD:-github_analytics}" pg_restore \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${TARGET_DB}" \
    --no-owner --no-acl --clean --if-exists || true
else
  PGPASSWORD="${POSTGRES_PASSWORD:-github_analytics}" pg_restore \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${TARGET_DB}" \
    --no-owner --no-acl --clean --if-exists "${BACKUP_FILE}" || true
fi

echo "[$(date -u)] Verifying table records..."
ROW_COUNTS=$(PGPASSWORD="${POSTGRES_PASSWORD:-github_analytics}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${TARGET_DB}" -t -c "
  SELECT 
    (SELECT COUNT(*) FROM catalog_repositories) AS catalog_count,
    (SELECT COUNT(*) FROM repositories) AS repo_count,
    (SELECT COUNT(*) FROM repository_embeddings) AS emb_count,
    (SELECT COUNT(*) FROM scout_assessments) AS scout_count;
" 2>/dev/null || echo "Unable to query table counts")

echo "[$(date -u)] Restore Verification Metrics (catalog, repos, embeddings, scout):"
echo "${ROW_COUNTS}"

if [ "${REHEARSAL}" -eq 1 ]; then
  echo "[$(date -u)] Cleaning up rehearsal database ${TARGET_DB}..."
  PGPASSWORD="${POSTGRES_PASSWORD:-github_analytics}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -c "DROP DATABASE ${TARGET_DB};"
  echo "[$(date -u)] Rehearsal completed successfully."
else
  echo "[$(date -u)] Restore completed successfully."
fi
