#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 BACKUP.dump" >&2
  exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
backend_dir=$(dirname -- "$script_dir")
backup=$1

if [ ! -s "$backup" ]; then
  echo "backup does not exist or is empty: $backup" >&2
  exit 2
fi
if [ ! -s "$backup.sha256" ]; then
  echo "backup checksum does not exist: $backup.sha256" >&2
  exit 2
fi

shasum -a 256 -c "$backup.sha256"

restore_db="social_ops_restore_$(date -u +%Y%m%d%H%M%S)_$$"
case "$restore_db" in
  social_ops_restore_[0-9]*_[0-9]*) ;;
  *)
    echo "generated restore database name is unsafe" >&2
    exit 1
    ;;
esac

cleanup_restore() {
  cd "$backend_dir"
  docker compose exec -T postgres \
    dropdb \
    --if-exists \
    --force \
    --username=social \
    "$restore_db" >/dev/null
}
trap cleanup_restore EXIT HUP INT TERM

cd "$backend_dir"
docker compose exec -T postgres \
  createdb \
  --username=social \
  "$restore_db"
docker compose exec -T postgres \
  pg_restore \
  --exit-on-error \
  --no-owner \
  --no-acl \
  --username=social \
  --dbname="$restore_db" <"$backup"

expected_revision=$(uv run python -c \
  'from app.db.migration_state import expected_schema_revision; print(expected_schema_revision())')
actual_revision=$(docker compose exec -T postgres \
  psql \
  --tuples-only \
  --no-align \
  --username=social \
  --dbname="$restore_db" \
  --command='SELECT version_num FROM alembic_version')

if [ "$actual_revision" != "$expected_revision" ]; then
  echo "schema revision mismatch: expected $expected_revision, got $actual_revision" >&2
  exit 1
fi

table_count=$(docker compose exec -T postgres \
  psql \
  --tuples-only \
  --no-align \
  --username=social \
  --dbname="$restore_db" \
  --command="SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
workspace_count=$(docker compose exec -T postgres \
  psql \
  --tuples-only \
  --no-align \
  --username=social \
  --dbname="$restore_db" \
  --command='SELECT count(*) FROM workspaces')
active_job_count=$(docker compose exec -T postgres \
  psql \
  --tuples-only \
  --no-align \
  --username=social \
  --dbname="$restore_db" \
  --command="SELECT count(*) FROM sync_jobs WHERE status IN ('pending','running','retry_wait')")

if [ "$table_count" -lt 1 ]; then
  echo "restored database contains no public tables" >&2
  exit 1
fi

echo "restore_rehearsal=passed"
echo "schema_revision=$actual_revision"
echo "public_tables=$table_count"
echo "workspaces=$workspace_count"
echo "active_jobs=$active_job_count"
