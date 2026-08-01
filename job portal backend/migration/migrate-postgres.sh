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

required_variable SOURCE_DATABASE_URL
required_variable TARGET_DATABASE_URL
required_variable ALLOW_TARGET_REPLACE

if [ "$ALLOW_TARGET_REPLACE" != "YES_I_HAVE_VERIFIED_THE_TARGET" ]; then
  echo "Refusing to replace the target without the explicit safety acknowledgement." >&2
  exit 2
fi

case "$SOURCE_DATABASE_URL" in
  postgresql+psycopg2://*)
    source_url="postgresql://${SOURCE_DATABASE_URL#postgresql+psycopg2://}"
    ;;
  *)
    source_url="$SOURCE_DATABASE_URL"
    ;;
esac
case "$TARGET_DATABASE_URL" in
  postgresql+psycopg2://*)
    target_url="postgresql://${TARGET_DATABASE_URL#postgresql+psycopg2://}"
    ;;
  *)
    target_url="$TARGET_DATABASE_URL"
    ;;
esac

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
