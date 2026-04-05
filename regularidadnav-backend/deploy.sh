#!/usr/bin/env bash
set -euo pipefail

SERVER="root@164.92.191.140"
REMOTE_DIR="/opt/regularidadnav"
DOMAIN="regularidadnav.elena-agents.com"

echo "=== RegularidadNav Deploy ==="

# 1. Copy files to server
echo "[1/5] Copying files to server..."
ssh "$SERVER" "mkdir -p $REMOTE_DIR"
rsync -avz --delete \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '.env' \
  "$(dirname "$0")/" "$SERVER:$REMOTE_DIR/"

# 2. Create .env if not exists
echo "[2/5] Setting up environment..."
ssh "$SERVER" "
  cd $REMOTE_DIR
  if [ ! -f .env ]; then
    PASS=\$(openssl rand -hex 16)
    cat > .env <<EOF
POSTGRES_USER=regularidadnav
POSTGRES_PASSWORD=\$PASS
POSTGRES_DB=regularidadnav
DATABASE_URL=postgresql+asyncpg://regularidadnav:\$PASS@db:5432/regularidadnav
EOF
    echo '  .env created with generated password'
  else
    echo '  .env already exists, skipping'
  fi
"

# 3. Ensure nginx-net network exists
echo "[3/5] Setting up Docker network..."
ssh "$SERVER" "docker network create nginx-net 2>/dev/null || true"

# 4. Copy nginx config
echo "[4/5] Configuring Nginx..."
ssh "$SERVER" "
  cp $REMOTE_DIR/nginx/regularidadnav.conf /etc/nginx/sites-available/regularidadnav.conf 2>/dev/null || \
  cp $REMOTE_DIR/nginx/regularidadnav.conf /etc/nginx/conf.d/regularidadnav.conf 2>/dev/null || true

  if [ -d /etc/nginx/sites-enabled ]; then
    ln -sf /etc/nginx/sites-available/regularidadnav.conf /etc/nginx/sites-enabled/regularidadnav.conf
  fi

  nginx -t && systemctl reload nginx || echo 'WARN: nginx reload failed, check config'
"

# 5. Build and start
echo "[5/5] Building and starting services..."
ssh "$SERVER" "
  cd $REMOTE_DIR
  docker compose pull db
  docker compose build api
  docker compose up -d

  echo ''
  echo '=== Waiting for API to start... ==='
  sleep 5

  # Health check
  if curl -sf http://localhost:8001/api/health > /dev/null 2>&1; then
    echo 'API is running!'
  else
    echo 'WARN: API health check failed, checking logs...'
    docker compose logs --tail=20 api
  fi

  # Create a test regatta
  echo ''
  echo '=== Creating test regatta ==='
  RESULT=\$(curl -sf -X POST http://localhost:8001/api/regatas \
    -H 'Content-Type: application/json' \
    -d '{
      \"nombre\": \"Regata de prueba\",
      \"fecha\": \"2026-04-05\",
      \"club_organizador\": \"Club Náutico Test\",
      \"balizas\": [
        {\"nombre\": \"Puerto Moraira\", \"lat\": 38.683, \"lng\": 0.129, \"orden\": 0},
        {\"nombre\": \"Cabo de la Nao\", \"lat\": 38.7344, \"lng\": 0.235, \"orden\": 1},
        {\"nombre\": \"WP Intermedio\", \"lat\": 38.91, \"lng\": 0.68, \"orden\": 2},
        {\"nombre\": \"Sur de Ibiza\", \"lat\": 38.88, \"lng\": 1.25, \"orden\": 3},
        {\"nombre\": \"Puerto La Savina\", \"lat\": 38.728, \"lng\": 1.4055, \"orden\": 4}
      ]
    }')

  CLAVE=\$(echo \"\$RESULT\" | python3 -c \"import sys,json; print(json.load(sys.stdin)['clave_acceso'])\" 2>/dev/null || echo 'ERROR')

  echo ''
  echo '╔══════════════════════════════════════════════╗'
  echo '║  RegularidadNav desplegado correctamente!    ║'
  echo '╠══════════════════════════════════════════════╣'
  echo \"║  API:    http://$DOMAIN/api/health           ║\"
  echo \"║  Docs:   http://$DOMAIN/docs                 ║\"
  echo \"║  WS:     ws://$DOMAIN/ws/{clave}             ║\"
  echo '║                                              ║'
  echo \"║  Clave regata test: \$CLAVE                   ║\"
  echo '╚══════════════════════════════════════════════╝'
"
