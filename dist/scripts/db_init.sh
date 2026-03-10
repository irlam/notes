#!/usr/bin/env bash
# =============================================================================
# scripts/db_init.sh — Bootstrap the SQLite database for a fresh install.
#
# Usage:
#   bash scripts/db_init.sh
#
# What it does:
#   - Loads DATABASE_PATH from .env (or uses the default 'notes.db').
#   - Checks that the database does not already contain application tables.
#   - Applies schema.sql to create all tables and indexes.
#   - Does NOT drop or overwrite existing data.
#
# For MySQL installs, use:  mysql -u <user> -p <db> < db/schema.mysql.sql
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve repo root (one level up from this script's directory)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# Load .env if present
# ---------------------------------------------------------------------------
ENV_FILE="${REPO_ROOT}/.env"
if [[ -f "${ENV_FILE}" ]]; then
    # Export only valid KEY=VALUE lines (ignore comments and blank lines)
    set -o allexport
    # shellcheck disable=SC1090
    source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${ENV_FILE}" | sed 's/#.*//')
    set +o allexport
fi

DB_PATH="${DATABASE_PATH:-${REPO_ROOT}/notes.db}"
SCHEMA_FILE="${REPO_ROOT}/schema.sql"

echo "=== Notes DB Bootstrap ==="
echo "Database : ${DB_PATH}"
echo "Schema   : ${SCHEMA_FILE}"
echo ""

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
if [[ ! -f "${SCHEMA_FILE}" ]]; then
    echo "ERROR: schema.sql not found at ${SCHEMA_FILE}" >&2
    exit 1
fi

PYTHON=$(command -v python3 || command -v python || true)
if [[ -z "${PYTHON}" ]]; then
    echo "ERROR: python3 not found in PATH." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Check if database already contains tables (safe guard)
# ---------------------------------------------------------------------------
EXISTING=$("${PYTHON}" - <<EOF
import sqlite3, sys
db = sqlite3.connect('${DB_PATH}')
rows = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
db.close()
print(len(rows))
EOF
)

if [[ "${EXISTING}" -gt 0 ]]; then
    echo "INFO: Database already contains ${EXISTING} table(s). Skipping schema init."
    echo "      To reset a DEV database, use: bash scripts/db_reset_dev.sh"
    echo "      To apply migrations to an existing install, see: migrations/README.md"
    exit 0
fi

# ---------------------------------------------------------------------------
# Apply schema
# ---------------------------------------------------------------------------
"${PYTHON}" - <<EOF
import sqlite3
db = sqlite3.connect('${DB_PATH}')
with open('${SCHEMA_FILE}') as f:
    db.executescript(f.read())
db.commit()
db.close()
print("Database initialised successfully from schema.sql")
EOF

echo ""
echo "Next steps:"
echo "  1. flask create-user <username>   # create your first user"
echo "  2. flask run                      # start the dev server"
