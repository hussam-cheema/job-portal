#!/bin/sh
set -eu

required_variable() {
  variable_name="$1"
  eval "variable_value=\${$variable_name:-}"
  if [ -z "$variable_value" ]; then
    echo "$variable_name is required" >&2
    exit 2
  fi
}

normalize_postgres_url() {
  case "$1" in
    postgresql+psycopg2://*)
      printf '%s\n' "postgresql://${1#postgresql+psycopg2://}"
      ;;
    *)
      printf '%s\n' "$1"
      ;;
  esac
}

backup_database() {
  required_variable BACKUP_DATABASE_URL
  required_variable R2_ENDPOINT
  required_variable R2_BUCKET_NAME
  required_variable R2_ACCESS_KEY_ID
  required_variable R2_SECRET_ACCESS_KEY

  backup_url="$(normalize_postgres_url "$BACKUP_DATABASE_URL")"
  case "$backup_url" in
    *-pooler.*)
      echo "Use the Neon direct (non-pooler) URL for a logical backup." >&2
      exit 2
      ;;
    *neon.tech*)
      ;;
    *)
      if [ "${BACKUP_TEST_ALLOW_NON_NEON:-}" != "YES_LOCAL_TEST_ONLY" ]; then
        echo "Refusing to back up a database that is not hosted by Neon." >&2
        exit 2
      fi
      ;;
  esac

  backup_prefix="${R2_BACKUP_PREFIX:-production-backups}"
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  dump_file="/tmp/job-portal-${timestamp}.dump"
  checksum_file="${dump_file}.sha256"
  object_key="${backup_prefix%/}/job-portal-${timestamp}.dump"

  echo "Checking Neon direct-database connectivity..."
  pg_isready --dbname="$backup_url" --timeout=30

  echo "Creating a transaction-consistent custom-format database backup..."
  pg_dump \
    --dbname="$backup_url" \
    --format=custom \
    --file="$dump_file" \
    --schema=public \
    --no-owner \
    --no-privileges

  echo "Validating the backup archive..."
  pg_restore --list "$dump_file" >/dev/null
  sha256sum "$dump_file" > "$checksum_file"

  export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
  export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
  export AWS_DEFAULT_REGION=auto

  echo "Uploading the backup and checksum to Cloudflare R2..."
  aws --endpoint-url "$R2_ENDPOINT" s3 cp \
    "$dump_file" "s3://${R2_BUCKET_NAME}/${object_key}" \
    --only-show-errors
  aws --endpoint-url "$R2_ENDPOINT" s3 cp \
    "$checksum_file" "s3://${R2_BUCKET_NAME}/${object_key}.sha256" \
    --content-type text/plain \
    --only-show-errors

  remote_size="$(
    aws --endpoint-url "$R2_ENDPOINT" s3api head-object \
      --bucket "$R2_BUCKET_NAME" \
      --key "$object_key" \
      --query ContentLength \
      --output text
  )"
  local_size="$(wc -c < "$dump_file" | tr -d ' ')"
  if [ "$remote_size" != "$local_size" ]; then
    echo "Backup verification failed: local size $local_size, remote size $remote_size." >&2
    exit 3
  fi

  echo "Backup completed and verified."
  echo "R2 object: s3://${R2_BUCKET_NAME}/${object_key}"
  echo "Bytes: ${local_size}"
}

case "${MIGRATION_MODE:-copy}" in
  backup)
    backup_database
    exit 0
    ;;
  copy)
    ;;
  *)
    echo "MIGRATION_MODE must be 'copy' or 'backup'." >&2
    exit 2
    ;;
esac

required_variable SOURCE_DATABASE_URL
required_variable TARGET_DATABASE_URL
required_variable ALLOW_TARGET_REPLACE

if [ "$ALLOW_TARGET_REPLACE" != "YES_I_HAVE_VERIFIED_THE_TARGET" ]; then
  echo "Refusing to replace the target without the explicit safety acknowledgement." >&2
  exit 2
fi

source_url="$(normalize_postgres_url "$SOURCE_DATABASE_URL")"
target_url="$(normalize_postgres_url "$TARGET_DATABASE_URL")"

case "$target_url" in
  *-pooler.*)
    echo "Use Neon's direct (non-pooler) URL for pg_restore." >&2
    exit 2
    ;;
  *neon.tech*)
    ;;
  *)
    if [ "${MIGRATION_TEST_ALLOW_NON_NEON:-}" = "YES_LOCAL_TEST_ONLY" ]; then
      echo "Local integration-test target override enabled."
    else
      echo "Refusing to replace a target that is not a Neon database." >&2
      exit 2
    fi
    ;;
esac

dump_file="/tmp/job-portal-production.dump"

echo "Checking source and target connectivity..."
pg_isready --dbname="$source_url" --timeout=30
pg_isready --dbname="$target_url" --timeout=30

echo "Creating a transaction-consistent PostgreSQL 16 snapshot..."
pg_dump \
  --dbname="$source_url" \
  --format=custom \
  --file="$dump_file" \
  --schema=public \
  --no-owner \
  --no-privileges

echo "Replacing the Neon public schema from the snapshot..."
pg_restore \
  --dbname="$target_url" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --exit-on-error \
  --single-transaction \
  "$dump_file"

echo "Comparing public tables and exact row counts..."
source_tables="/tmp/source-tables.txt"
target_tables="/tmp/target-tables.txt"
psql "$source_url" -X -qAtc \
  "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename" \
  > "$source_tables"
psql "$target_url" -X -qAtc \
  "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename" \
  > "$target_tables"

if ! cmp -s "$source_tables" "$target_tables"; then
  echo "Source and target public table sets differ:" >&2
  diff -u "$source_tables" "$target_tables" >&2 || true
  exit 3
fi

mismatches=0
while IFS= read -r table_name; do
  case "$table_name" in
    *[!A-Za-z0-9_]*)
      echo "Unsafe table name encountered: $table_name" >&2
      exit 3
      ;;
  esac
  source_count="$(psql "$source_url" -X -qAtc "SELECT count(*) FROM public.\"$table_name\"")"
  target_count="$(psql "$target_url" -X -qAtc "SELECT count(*) FROM public.\"$table_name\"")"
  if [ "$source_count" != "$target_count" ]; then
    echo "Row-count mismatch public.$table_name source=$source_count target=$target_count" >&2
    mismatches=$((mismatches + 1))
  fi
done < "$source_tables"

if [ "$mismatches" -ne 0 ]; then
  echo "Database parity failed with $mismatches mismatch(es)." >&2
  exit 3
fi

echo "Database transfer and parity verification completed successfully."
