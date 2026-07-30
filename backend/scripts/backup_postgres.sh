#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 OUTPUT.dump" >&2
  exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
backend_dir=$(dirname -- "$script_dir")
output=$1

case "$output" in
  ""|"/"|".")
    echo "refusing unsafe backup output path" >&2
    exit 2
    ;;
esac

if [ -e "$output" ] || [ -e "$output.sha256" ]; then
  echo "backup output already exists: $output" >&2
  exit 2
fi

output_dir=$(dirname -- "$output")
mkdir -p -- "$output_dir"
partial="${output}.partial.$$"

cleanup_partial() {
  rm -f -- "$partial"
}
trap cleanup_partial EXIT HUP INT TERM

cd "$backend_dir"
docker compose exec -T postgres \
  pg_dump \
  --format=custom \
  --compress=9 \
  --no-owner \
  --no-acl \
  --username=social \
  --dbname=social_ops >"$partial"

if [ ! -s "$partial" ]; then
  echo "pg_dump produced an empty backup" >&2
  exit 1
fi

mv -- "$partial" "$output"
shasum -a 256 "$output" >"$output.sha256"
trap - EXIT HUP INT TERM
echo "backup=$output"
echo "checksum=${output}.sha256"
