#!/usr/bin/env bash
#
# Back up the irreplaceable, un-versioned parts of a deployment before an
# update: the SQLite database, the .env file, and the Google service-account
# JSON credentials. The application code itself lives in git and is not backed
# up here.
#
# Usage:
#   bash scripts/backup.sh [APP_DIR]
#
# APP_DIR defaults to the directory this script lives in (its parent), so
# running it from inside a checkout "just works". Backups are written to
#   <APP_DIR>/../order_app_backups/backup_<timestamp>/
#
set -euo pipefail

# Resolve APP_DIR: explicit arg, else the repo root (parent of scripts/).
if [ "${1:-}" != "" ]; then
    APP_DIR="$1"
else
    APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "$APP_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
DEST="$(cd .. && pwd)/order_app_backups/backup_${STAMP}"
mkdir -p "$DEST"

echo "Backing up: $APP_DIR"
echo "Into:       $DEST"
echo

# --- Database -------------------------------------------------------------
# Respect DATABASE_PATH from .env if set, otherwise default to app.db.
DB_PATH="app.db"
if [ -f .env ]; then
    ENV_DB="$(grep -E '^DATABASE_PATH=' .env | tail -n1 | cut -d= -f2- | tr -d '"'\'' ' || true)"
    [ -n "${ENV_DB:-}" ] && DB_PATH="$ENV_DB"
fi

if [ -f "$DB_PATH" ]; then
    DB_NAME="$(basename "$DB_PATH")"
    if command -v sqlite3 >/dev/null 2>&1; then
        # .backup takes a consistent snapshot even while the app is writing.
        sqlite3 "$DB_PATH" ".backup '$DEST/$DB_NAME'"
        echo "  database (consistent snapshot): $DB_PATH"
    else
        # Fallback: copy the DB plus its WAL/SHM sidecars so the copy is usable.
        cp -a "$DB_PATH" "$DEST/"
        [ -f "${DB_PATH}-wal" ] && cp -a "${DB_PATH}-wal" "$DEST/"
        [ -f "${DB_PATH}-shm" ] && cp -a "${DB_PATH}-shm" "$DEST/"
        echo "  database (file copy, sqlite3 not installed): $DB_PATH"
    fi
else
    echo "  WARNING: no database found at $DB_PATH"
fi

# --- Secrets & config -----------------------------------------------------
[ -f .env ] && cp -a .env "$DEST/" && echo "  config: .env"

shopt -s nullglob
for f in *.json; do
    cp -a "$f" "$DEST/"
    echo "  credentials: $f"
done
shopt -u nullglob

# --- Record git state so you know exactly what to roll back to -------------
git rev-parse HEAD > "$DEST/GIT_HEAD.txt" 2>/dev/null \
    && echo "  git HEAD recorded: $(cat "$DEST/GIT_HEAD.txt")" \
    || echo "not a git repository" > "$DEST/GIT_HEAD.txt"

echo
echo "Backup complete."
ls -la "$DEST"
