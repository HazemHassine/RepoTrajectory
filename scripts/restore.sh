#!/usr/bin/env bash
set -euo pipefail

# Rehearsal uses an isolated database and retains it on failure for inspection.
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ] || { [ "$#" -eq 2 ] && [ "$2" != "--rehearsal" ]; }; then
  echo "Usage: $0 <backup_file> [--rehearsal]" >&2
  exit 1
fi
BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-github_analytics}"
TARGET_DB="${POSTGRES_DB:-github_analytics}"
export PGPASSWORD="${POSTGRES_PASSWORD:-github_analytics}"
REHEARSAL=0
if [ "${2:-}" = "--rehearsal" ]; then
  REHEARSAL=1
  TARGET_DB="repotrajectory_rehearsal_$(date +%s)_$$"
  psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $TARGET_DB;"
fi
trap 'echo "Restore failed for $TARGET_DB. No success reported; inspect the error above." >&2' ERR
echo "Restoring $BACKUP_FILE into $TARGET_DB"
RESTORE_ARGS=(-h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$TARGET_DB"
  --exit-on-error --single-transaction --no-owner --no-acl --clean --if-exists)
if [[ "$BACKUP_FILE" == *.gz ]]; then
  gunzip -c "$BACKUP_FILE" | pg_restore "${RESTORE_ARGS[@]}"
else
  pg_restore "${RESTORE_ARGS[@]}" "$BACKUP_FILE"
fi
echo "Verifying schema revision and every public table..."
psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$TARGET_DB" -v ON_ERROR_STOP=1 <<'SQL'
SELECT version_num AS restored_schema_version FROM alembic_version;
SELECT format('SELECT %L AS table_name, count(*) AS row_count FROM %I.%I;',
              tablename, schemaname, tablename)
FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename
\gexec
SQL
if [ "$REHEARSAL" -eq 1 ]; then
  psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE $TARGET_DB;"
fi
echo "Restore completed successfully."
