#!/bin/bash
set -euo pipefail
cd /opt/capstone-traffic
umask 077
backup_dir=/var/backups/capstone-traffic
install -d -m 0700 "$backup_dir"
backup_file="$backup_dir/capstone-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose -f docker-compose.yml -f infra/aws/compose.cloud.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_file.tmp"
mv "$backup_file.tmp" "$backup_file"
find "$backup_dir" -type f -name 'capstone-*.dump' -mtime +7 -delete
