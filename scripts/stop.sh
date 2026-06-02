#!/usr/bin/env bash
#
# Policy Impact Engine — stop the full stack (Linux / macOS / WSL).
#
# Kills the backend + frontend started by start.sh (via their PID files),
# then brings the Docker containers down.
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi

echo "============================================"
echo "  Policy Impact Engine - Stopping..."
echo "============================================"

for svc in backend frontend; do
  PID_FILE="${ROOT_DIR}/.${svc}.pid"
  if [ -f "${PID_FILE}" ]; then
    PID="$(cat "${PID_FILE}")"
    if kill "${PID}" >/dev/null 2>&1; then
      echo "  Stopped ${svc} (pid ${PID})."
    fi
    rm -f "${PID_FILE}"
  else
    echo "  No ${svc} pid file — skipping (was it started via start.sh?)."
  fi
done

echo "  Stopping Docker containers..."
( cd "${ROOT_DIR}" && ${DC} down )

echo "============================================"
echo "  All services stopped."
echo "============================================"
