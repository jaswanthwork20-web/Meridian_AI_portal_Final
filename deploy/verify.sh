#!/usr/bin/env bash
set -euo pipefail

cd "$APP_DIR"
docker compose ps --status running --services | grep -qx backend
docker compose ps --status running --services | grep -qx frontend
docker compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=10)"
docker compose exec -T frontend wget --spider --quiet http://127.0.0.1/health
curl --fail --silent --show-error http://127.0.0.1/health >/dev/null
echo 'Backend, frontend, and reverse-proxy health checks passed.'
