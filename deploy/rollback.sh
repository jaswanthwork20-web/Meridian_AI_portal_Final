#!/usr/bin/env bash
set -euo pipefail

cd "$APP_DIR"
test -s .previous_backend_image
test -s .previous_frontend_image
previous_backend=$(cat .previous_backend_image)
previous_frontend=$(cat .previous_frontend_image)
sed -i '/^BACKEND_IMAGE=/d; /^FRONTEND_IMAGE=/d' .env
printf 'BACKEND_IMAGE=%s\nFRONTEND_IMAGE=%s\n' "$previous_backend" "$previous_frontend" >> .env
chmod 600 .env
docker compose pull
docker compose up -d --no-build --remove-orphans
