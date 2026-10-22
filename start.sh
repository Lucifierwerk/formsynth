#!/usr/bin/env bash
# FormSynth — quick start (bash / macOS / Linux)
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/venv"
REQ_FILE="$BACKEND/requirements.txt"
REQ_STAMP="$VENV/.req_hash"
PKG_FILE="$FRONTEND/package.json"
PKG_STAMP="$FRONTEND/.pkg_hash"

# ── Python ────────────────────────────────────────────────────────────────────
PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
if [ -z "$PYTHON" ]; then
  echo "ERROR: Python 3 not found. Install Python 3.11+ and try again."
  exit 1
fi

# ── Node / npm ────────────────────────────────────────────────────────────────
if ! command -v npm &>/dev/null; then
  echo "ERROR: npm not found. Install Node.js 18+ and try again."
  exit 1
fi

# md5 differs between macOS (md5) and Linux (md5sum)
md5() {
  if command -v md5sum &>/dev/null; then
    md5sum "$1" | cut -d' ' -f1
  else
    command md5 -q "$1"
  fi
}

# ── Backend venv ──────────────────────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
  echo "Creating Python venv..."
  "$PYTHON" -m venv "$VENV"
fi

CURRENT_HASH=$(md5 "$REQ_FILE")
SAVED_HASH=$(cat "$REQ_STAMP" 2>/dev/null || echo "")

if [ "$CURRENT_HASH" != "$SAVED_HASH" ]; then
  echo "Installing backend dependencies..."
  "$VENV/bin/pip" install -q -r "$REQ_FILE"
  echo "$CURRENT_HASH" > "$REQ_STAMP"
else
  echo "Backend dependencies up to date."
fi

# ── Frontend deps ─────────────────────────────────────────────────────────────
PKG_HASH=$(md5 "$PKG_FILE")
PKG_SAVED=$(cat "$PKG_STAMP" 2>/dev/null || echo "")

if [ ! -d "$FRONTEND/node_modules" ] || [ "$PKG_HASH" != "$PKG_SAVED" ]; then
  echo "Installing frontend dependencies..."
  (cd "$FRONTEND" && npm install --silent)
  echo "$PKG_HASH" > "$PKG_STAMP"
else
  echo "Frontend dependencies up to date."
fi

# ── Launch ────────────────────────────────────────────────────────────────────
echo ""
echo "  Starting FormSynth..."
echo "  Frontend →  http://localhost:5173"
echo "  API docs →  http://localhost:8000/docs"
echo ""

(cd "$BACKEND" && "$VENV/bin/uvicorn" app.main:app --reload --port 8000) &
BACKEND_PID=$!

(cd "$FRONTEND" && npm run dev) &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

wait $BACKEND_PID $FRONTEND_PID
