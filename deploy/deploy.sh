#!/usr/bin/env bash
set -euo pipefail

cd "$APP_DIR"
test -f docker-compose.yml
: "${BACKEND_IMAGE:?Backend image is required}"
: "${FRONTEND_IMAGE:?Frontend image is required}"

previous_backend=$(sed -n 's/^BACKEND_IMAGE=//p' .env 2>/dev/null | tail -n 1 || true)
previous_frontend=$(sed -n 's/^FRONTEND_IMAGE=//p' .env 2>/dev/null | tail -n 1 || true)
if [ -n "$previous_backend" ] && [ -n "$previous_frontend" ]; then
  printf '%s\n' "$previous_backend" > .previous_backend_image
  printf '%s\n' "$previous_frontend" > .previous_frontend_image
  chmod 600 .previous_backend_image .previous_frontend_image
fi

secret_json=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" \
  --region "$AWS_REGION" \
  --query SecretString \
  --output text)
test -n "$secret_json"
printf '%s' "$secret_json" | python3 -c '
import json
import re
import sys

secrets = json.load(sys.stdin)
reserved = {"ENVIRONMENT", "AWS_REGION", "DATABASE_PATH", "BACKEND_IMAGE", "FRONTEND_IMAGE"}
for key, value in secrets.items():
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or key in reserved:
        continue
    if isinstance(value, (dict, list)):
        value = json.dumps(value, separators=(",", ":"))
    else:
        value = str(value)
    print(f"{key}={json.dumps(value)}")
' > .env

grep -q '^JWT_SECRET=' .env
printf 'ENVIRONMENT=production\nAWS_REGION=%s\nDATABASE_PATH=/app/backend/data/shopmart.db\nBACKEND_IMAGE=%s\nFRONTEND_IMAGE=%s\n' \
  "$AWS_REGION" "$BACKEND_IMAGE" "$FRONTEND_IMAGE" >> .env
chmod 600 .env

docker compose pull
docker compose up -d --no-build --remove-orphans
docker compose ps
