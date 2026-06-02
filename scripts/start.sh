#!/usr/bin/env bash
#
# Policy Impact Engine — start the full stack (Linux / macOS / WSL).
#
# Brings up Postgres + Redis, then launches the backend (:8001) and
# frontend (:3000). The backend's lifespan auto-creates tables + applies
# additive migrations + runs idempotent backfills on startup, so the
# schema is always current. Logs stream to backend.log / frontend.log.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"

PYTHON="$(command -v python3 || command -v python || true)"
if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi

echo "============================================"
echo "  Policy Impact Engine - Starting..."
echo "============================================"

echo "[1/3] Starting Docker containers (PostgreSQL + Redis)..."
( cd "${ROOT_DIR}" && ${DC} up -d db redis )

echo "[2/3] Waiting for PostgreSQL..."
PG_CID="$(cd "${ROOT_DIR}" && ${DC} ps -q db)"
for i in $(seq 1 30); do
  if [ -n "${PG_CID}" ] && docker exec "${PG_CID}" pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 2
done

echo "[3/3] Starting backend (:8001) and frontend (:3000)..."
( cd "${BACKEND_DIR}" && nohup ${PYTHON} -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload \
    > "${BACKEND_DIR}/backend.log" 2>&1 & echo $! > "${ROOT_DIR}/.backend.pid" )
( cd "${FRONTEND_DIR}" && nohup npm run dev \
    > "${FRONTEND_DIR}/frontend.log" 2>&1 & echo $! > "${ROOT_DIR}/.frontend.pid" )

cat <<EOF

============================================
  All services starting!
  Backend:  http://localhost:8001  (logs: backend/backend.log)
  Frontend: http://localhost:3000  (logs: frontend/frontend.log)
  Stop with: scripts/stop.sh
============================================
EOF
