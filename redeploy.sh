#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

SKIP_PULL=false

for arg in "$@"; do
  case "${arg}" in
    --no-pull)
      SKIP_PULL=true
      ;;
    -h|--help)
      echo "Usage: ./redeploy.sh [--no-pull]"
      echo "  --no-pull   Skip 'git pull origin main' and only redeploy docker services."
      exit 0
      ;;
    *)
      echo "Unknown option: ${arg}" >&2
      echo "Usage: ./redeploy.sh [--no-pull]" >&2
      exit 1
      ;;
  esac
done

if [ "${SKIP_PULL}" = false ]; then
  git pull origin main
fi

docker compose down
docker compose up --build -d
