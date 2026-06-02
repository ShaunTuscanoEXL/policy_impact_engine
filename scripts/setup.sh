#!/usr/bin/env bash
#
# Policy Impact Engine — one-time setup for a new system (Linux / macOS / WSL).
#
# Mirrors scripts/setup.bat but for POSIX shells, and fixes the schema-init
# step so a fresh database gets EVERY table (including audit_events) and
# every additive column before the seed runs.
#
# What it does:
#   1. Verify prerequisites (python3, node, docker)
#   2. Start the Postgres + Redis containers
#   3. Wait until Postgres actually accepts connections
#   4. Install backend Python deps
#   5. Create backend/.env if missing
#   6. Create the DB schema + apply additive migrations (scripts.init_db)
#   7. Seed the loan-records corpus (100k by default; override with SEED_COUNT)
#   8. Install frontend deps
#
# Re-running is safe: deps re-install is idempotent, init_db is idempotent,
# and the seed skips if records already exist (pass --force to reseed).
#
set -euo pipefail

# ── Resolve paths ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
SEED_COUNT="${SEED_COUNT:-100000}"

# ── Tool detection (python3 vs python, docker compose vs docker-compose) ───
PYTHON="$(command -v python3 || command -v python || true)"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  DC=""
fi

say()  { printf '\n\033[1;36m%s\033[0m\n' "$*"; }
ok()   { printf '      \033[0;32m%s\033[0m\n' "$*"; }
die()  { printf '\n\033[0;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

echo "============================================"
echo "  Policy Impact Engine - One-Time Setup"
echo "============================================"

# ── [1/8] Prerequisites ────────────────────────────────────────────────────
say "[1/8] Checking prerequisites..."
[ -n "${PYTHON}" ] || die "Python 3.11+ not found. Install from https://python.org"
command -v node >/dev/null 2>&1 || die "Node.js 18+ not found. Install from https://nodejs.org"
[ -n "${DC}" ] || die "Docker (with compose) not found. Install Docker Desktop / Engine."
ok "python: $(${PYTHON} --version 2>&1) | node: $(node --version) | docker: $(docker --version | cut -d, -f1)"

# ── [2/8] Start data services ──────────────────────────────────────────────
say "[2/8] Starting Docker containers (PostgreSQL + Redis)..."
( cd "${ROOT_DIR}" && ${DC} up -d db redis ) || die "Failed to start containers. Is the Docker daemon running?"
ok "Containers started."

# ── [3/8] Wait for Postgres to accept connections ──────────────────────────
say "[3/8] Waiting for PostgreSQL to be ready..."
PG_CID="$(cd "${ROOT_DIR}" && ${DC} ps -q db)"
for i in $(seq 1 30); do
  if [ -n "${PG_CID}" ] && docker exec "${PG_CID}" pg_isready -U postgres >/dev/null 2>&1; then
    ok "PostgreSQL ready."
    break
  fi
  if [ "$i" -eq 30 ]; then die "PostgreSQL did not become ready in 60s."; fi
  sleep 2
done

# ── [4/8] Backend deps ──────────────────────────────────────────────────────
say "[4/8] Installing backend Python dependencies..."
( cd "${BACKEND_DIR}" && ${PYTHON} -m pip install -e ".[dev]" ) || die "pip install failed."
ok "Backend dependencies installed."

# ── [5/8] Environment file ──────────────────────────────────────────────────
say "[5/8] Setting up environment..."
ENV_FILE="${BACKEND_DIR}/.env"
if [ ! -f "${ENV_FILE}" ]; then
  cat > "${ENV_FILE}" <<'EOF'
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/policy_impact_engine
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=your-openai-key-here
EOF
  ok "Created backend/.env — IMPORTANT: set your OPENAI_API_KEY before extracting rules."
else
  ok "backend/.env already exists, skipping."
fi

# ── [6/8] Schema: create all tables + apply additive migrations ─────────────
# Uses the app's own migration logic so audit_events + every Slice 1/7
# column exist BEFORE seeding. (The old setup.bat used a broken sync
# create_all against an async engine — this is the corrected path.)
say "[6/8] Creating database schema + applying migrations..."
( cd "${BACKEND_DIR}" && ${PYTHON} -m scripts.init_db ) || die "Schema initialization failed."
ok "Schema ready."

# ── [7/8] Seed loan records ─────────────────────────────────────────────────
say "[7/8] Seeding ${SEED_COUNT} synthetic loan records (this can take a couple of minutes)..."
( cd "${BACKEND_DIR}" && ${PYTHON} -m scripts.seed_loan_records --count="${SEED_COUNT}" ) \
  && ok "Loan records seeded." \
  || ok "Seed skipped or partial (records may already exist; rerun with --force to reseed)."

# ── [8/8] Frontend deps ─────────────────────────────────────────────────────
say "[8/8] Installing frontend dependencies..."
( cd "${FRONTEND_DIR}" && npm install ) || die "npm install failed."
ok "Frontend dependencies installed."

cat <<EOF

============================================
  Setup Complete!
============================================

  Next steps:
    1. Edit backend/.env and set your OPENAI_API_KEY
    2. Start the stack:   scripts/start.sh
       (or manually: backend on :8001, frontend on :3000)

  The backend auto-applies any pending migrations + idempotent
  backfills on every startup, so the schema stays current.
============================================
EOF
