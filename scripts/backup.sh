#!/usr/bin/env bash
# Backs up the irreplaceable Postgres data to S3. Run from the repo dir on the EC2 host, e.g. cron:
#   0 3 * * * cd /opt/app && ./scripts/backup.sh >> /var/log/app-backup.log 2>&1
#
# Qdrant vectors are intentionally NOT backed up here — they are reconstructable by re-ingesting the
# sources, which live durably in S3. Postgres holds the relational data that cannot be regenerated.
set -euo pipefail

# Read only the vars we need, rather than sourcing the whole secrets file as shell (which breaks on
# values containing spaces, quotes or $).
read_env() { grep -E "^$1=" .env.prod | head -n1 | cut -d= -f2- || true; }
S3_BUCKET=$(read_env S3_BUCKET)
POSTGRES_USER=$(read_env POSTGRES_USER)
POSTGRES_DB=$(read_env POSTGRES_DB)
: "${S3_BUCKET:?set S3_BUCKET in .env.prod}"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DUMP="/tmp/pg-${STAMP}.sql.gz"
COMPOSE="docker compose --env-file .env.prod -f docker-compose.prod.yml"

echo "[$(date -u)] dumping Postgres..."
# pipefail makes a pg_dump failure abort the script before any upload, so a broken dump never
# overwrites a good backup with an empty/truncated file.
$COMPOSE exec -T postgres pg_dump -U "${POSTGRES_USER:-app}" "${POSTGRES_DB:-app}" | gzip > "$DUMP"

echo "[$(date -u)] uploading to s3://${S3_BUCKET}/backups/ ..."
aws s3 cp "$DUMP" "s3://${S3_BUCKET}/backups/pg-${STAMP}.sql.gz"
rm -f "$DUMP"
echo "[$(date -u)] backup complete."
