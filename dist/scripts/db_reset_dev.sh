#!/usr/bin/env bash
# =============================================================================
# scripts/db_reset_dev.sh — DEV-ONLY: Wipe and reinitialise the database.
#
# ██████████████████████████████████████████████████████████████████████████
# ⚠️  WARNING: THIS SCRIPT PERMANENTLY DELETES ALL DATA IN THE DATABASE. ⚠️
# ██████████████████████████████████████████████████████████████████████████
#
# This script is intended for local development only.
# It will REFUSE to run if FLASK_ENV=production.
#
# Usage:
#   bash scripts/db_reset_dev.sh
#
# The script will:
#   1. Detect the database path from .env or default.
#   2. Refuse to run in production (FLASK_ENV=production).
#   3. Prompt for explicit typed confirmation before deleting anything.
#   4. Delete the existing database file (if any).
#   5. Re-apply schema.sql from scratch.
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve repo root
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# Load .env if present
# ---------------------------------------------------------------------------
ENV_FILE="${REPO_ROOT}/.env"
if [[ -f "${ENV_FILE}" ]]; then
    set -o allexport
    # shellcheck disable=SC1090
    source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${ENV_FILE}" | sed 's/#.*//')
    set +o allexport
fi

DB_PATH="${DATABASE_PATH:-${REPO_ROOT}/notes.db}"
SCHEMA_FILE="${REPO_ROOT}/schema.sql"
FLASK_ENV="${FLASK_ENV:-development}"

echo "==================================================="
echo "  ⚠️  DEV-ONLY: Database Reset Script"
echo "==================================================="
echo ""
echo "  Environment : ${FLASK_ENV}"
echo "  Database    : ${DB_PATH}"
echo ""

# ---------------------------------------------------------------------------
# Refuse to run in production
# ---------------------------------------------------------------------------
if [[ "${FLASK_ENV}" == "production" ]]; then
    echo "ERROR: This script refuses to run when FLASK_ENV=production." >&2
    echo "       If you genuinely need to reset a production DB, do it manually." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Explicit confirmation
# ---------------------------------------------------------------------------
echo "  ⚠️  ALL DATA IN THE DATABASE WILL BE PERMANENTLY DELETED. ⚠️"
echo ""
echo "  Type exactly:  RESET DEV DB"
echo "  then press Enter to continue, or Ctrl-C to abort."
echo ""
read -r CONFIRM

if [[ "${CONFIRM}" != "RESET DEV DB" ]]; then
    echo "Confirmation did not match. Aborting. No changes made."
    exit 1
fi

# ---------------------------------------------------------------------------
# Delete existing database
# ---------------------------------------------------------------------------
if [[ -f "${DB_PATH}" ]]; then
    echo ""
    echo "Deleting: ${DB_PATH}"
    rm -f "${DB_PATH}"
fi

# ---------------------------------------------------------------------------
# Re-apply schema
# ---------------------------------------------------------------------------
PYTHON=$(command -v python3 || command -v python || true)
if [[ -z "${PYTHON}" ]]; then
    echo "ERROR: python3 not found in PATH." >&2
    exit 1
fi

if [[ ! -f "${SCHEMA_FILE}" ]]; then
    echo "ERROR: schema.sql not found at ${SCHEMA_FILE}" >&2
    exit 1
fi

"${PYTHON}" - <<EOF
import sqlite3
db = sqlite3.connect('${DB_PATH}')
with open('${SCHEMA_FILE}') as f:
    db.executescript(f.read())
db.commit()
db.close()
print("Database reset and reinitialised from schema.sql")
EOF

echo ""
echo "Done. Next:"
echo "  flask create-user <username>   # re-create your dev user"
