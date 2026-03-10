#!/usr/bin/env bash
# =============================================================================
# install.sh — Automated installer for the Notes application
#
# Usage:
#   bash install.sh [--dev] [--plesk]
#
# Options:
#   --dev     Set FLASK_ENV=development (default: production)
#   --plesk   Install dependencies into _pydeps/ instead of a venv
#             (required for Plesk Passenger deployments without a venv)
#
# What this script does:
#   1. Verifies Python 3.8+ is available
#   2. Creates a virtual environment (or _pydeps/ in --plesk mode)
#   3. Installs Python dependencies from requirements.txt
#   4. Creates .env from .env.example if it does not exist
#   5. Generates a cryptographically-secure SECRET_KEY automatically
#   6. Sets FLASK_ENV in .env
#   7. Initialises the SQLite database from schema.sql
#   8. Prompts to create the first user account
#   9. Sets safe file permissions on .env
#
# After installation:
#   Local dev  : bash run.sh
#   Plesk      : Restart the application in the Plesk Python panel
#   Gunicorn   : gunicorn --bind 0.0.0.0:8000 wsgi:application
#
# See DEPLOYMENT.md for full deployment instructions.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLASK_ENV_MODE="production"
USE_PLESK=false

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
for arg in "$@"; do
    case "$arg" in
        --dev)   FLASK_ENV_MODE="development" ;;
        --plesk) USE_PLESK=true ;;
    esac
done

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERR ]${NC}  $*"; }
step()  { echo -e "\n${BOLD}$*${NC}"; }

# Portable sed in-place replacement (handles both GNU/Linux and BSD/macOS)
_set_env() {
    local key="$1" value="$2" file=".env"
    if grep -q "^${key}=" "$file" 2>/dev/null; then
        if sed --version 2>/dev/null | grep -q GNU; then
            sed -i "s|^${key}=.*|${key}=${value}|" "$file"
        else
            sed -i '' "s|^${key}=.*|${key}=${value}|" "$file"
        fi
    else
        echo "${key}=${value}" >> "$file"
    fi
}

echo ""
echo -e "${BOLD}============================================================${NC}"
echo -e "${BOLD}  Notes App — Automated Installer${NC}"
echo -e "${BOLD}============================================================${NC}"
echo ""
echo "  Mode     : ${FLASK_ENV_MODE}"
echo "  Deps     : $([ "$USE_PLESK" = true ] && echo '_pydeps/ (Plesk)' || echo 'venv/')"
echo "  Directory: ${SCRIPT_DIR}"
echo ""

cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Step 1 — Verify Python 3.8+
# ---------------------------------------------------------------------------
step "Step 1 — Checking Python version"

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
if [[ -z "$PYTHON" ]]; then
    error "Python 3 is not installed or not in PATH."
    error "Install Python 3.8 or newer, then re-run this script."
    exit 1
fi

PY_MAJOR=$("$PYTHON" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')
PY_VERSION="${PY_MAJOR}.${PY_MINOR}"

if [[ "$PY_MAJOR" -lt 3 ]] || { [[ "$PY_MAJOR" -eq 3 ]] && [[ "$PY_MINOR" -lt 8 ]]; }; then
    error "Python 3.8+ is required. Found: Python ${PY_VERSION}"
    exit 1
fi
ok "Python ${PY_VERSION} found at ${PYTHON}"

# ---------------------------------------------------------------------------
# Step 2 — Set up dependencies
# ---------------------------------------------------------------------------
step "Step 2 — Installing dependencies"

if [[ "$USE_PLESK" = true ]]; then
    # Plesk mode: install into _pydeps/ (used by passenger_wsgi.py)
    mkdir -p _pydeps
    "$PYTHON" -m pip install --target _pydeps --upgrade --quiet -r requirements.txt
    ok "Dependencies installed into _pydeps/"
    info "passenger_wsgi.py will load packages from _pydeps/ automatically."
else
    # Standard mode: virtual environment
    if [[ ! -d "venv" ]]; then
        "$PYTHON" -m venv venv
        ok "Virtual environment created at ./venv"
    else
        ok "Virtual environment already exists at ./venv"
    fi

    # shellcheck disable=SC1091
    source venv/bin/activate

    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    ok "Dependencies installed into ./venv"
fi

# ---------------------------------------------------------------------------
# Step 3 — Create .env
# ---------------------------------------------------------------------------
step "Step 3 — Environment configuration"

if [[ ! -f ".env" ]]; then
    cp .env.example .env
    ok ".env created from .env.example"
else
    warn ".env already exists — skipping copy (existing values preserved)"
fi

# ---------------------------------------------------------------------------
# Step 4 — Generate SECRET_KEY
# ---------------------------------------------------------------------------
step "Step 4 — Generating SECRET_KEY"

CURRENT_KEY=$(grep -E '^SECRET_KEY=' .env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
if [[ -z "$CURRENT_KEY" ]] || [[ "$CURRENT_KEY" == "change-me-to-a-random-secret-key" ]]; then
    NEW_KEY=$("$PYTHON" -c "import secrets; print(secrets.token_hex(32))")
    _set_env "SECRET_KEY" "${NEW_KEY}"
    ok "Generated and saved new SECRET_KEY"
else
    ok "SECRET_KEY is already set — leaving unchanged"
fi

# ---------------------------------------------------------------------------
# Step 5 — Set FLASK_ENV
# ---------------------------------------------------------------------------
step "Step 5 — Setting FLASK_ENV"

_set_env "FLASK_ENV" "${FLASK_ENV_MODE}"
ok "FLASK_ENV set to ${FLASK_ENV_MODE}"

# ---------------------------------------------------------------------------
# Step 6 — Set SESSION_COOKIE_SECURE (production only)
# ---------------------------------------------------------------------------
if [[ "$FLASK_ENV_MODE" == "production" ]]; then
    _set_env "SESSION_COOKIE_SECURE" "true"
    info "SESSION_COOKIE_SECURE=true set (requires HTTPS in production)"
fi

# ---------------------------------------------------------------------------
# Step 7 — Initialise database
# ---------------------------------------------------------------------------
step "Step 7 — Initialising database"

bash scripts/db_init.sh

# ---------------------------------------------------------------------------
# Step 8 — Create uploads directory
# ---------------------------------------------------------------------------
step "Step 8 — Creating uploads directory"

mkdir -p uploads
ok "uploads/ directory ready"

# ---------------------------------------------------------------------------
# Step 9 — Set file permissions
# ---------------------------------------------------------------------------
step "Step 9 — Setting file permissions"

chmod 600 .env 2>/dev/null || warn "Could not chmod 600 .env (check manually)"
chmod 700 uploads  2>/dev/null || warn "Could not chmod 700 uploads"
chmod +x run.sh scripts/db_init.sh scripts/db_reset_dev.sh 2>/dev/null || true
ok "Permissions applied"

# ---------------------------------------------------------------------------
# Step 10 — Create first user (optional, interactive)
# ---------------------------------------------------------------------------
step "Step 10 — Create first user account"

echo ""
echo "  You can create an admin user now, or skip and do it later with:"
echo "    flask create-user <username>"
echo ""

FIRST_USER=""
if [[ -t 0 ]] && [[ -e /dev/tty ]]; then
    read -r -p "  Enter a username (leave blank to skip): " FIRST_USER </dev/tty || FIRST_USER=""
else
    info "Non-interactive environment detected — skipping user creation"
    info "Run 'flask create-user <username>' after installation to create a user"
fi

if [[ -n "$FIRST_USER" ]]; then
    export FLASK_APP=wsgi:app
    if [[ "$USE_PLESK" = false ]]; then
        # Ensure venv is active
        source venv/bin/activate 2>/dev/null || true
    fi
    flask create-user "$FIRST_USER"
    ok "User '${FIRST_USER}' created successfully"
else
    info "Skipped — run 'flask create-user <username>' to create a user later"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}============================================================${NC}"
echo -e "${GREEN}${BOLD}  Installation complete!${NC}"
echo -e "${BOLD}============================================================${NC}"
echo ""
echo "  Next steps:"
echo ""
if [[ "$USE_PLESK" = true ]]; then
    echo "  Plesk deployment:"
    echo "    1. Set the Application startup file to: passenger_wsgi.py"
    echo "    2. Restart the application in the Plesk Python panel"
    echo "    3. See DEPLOYMENT.md for the full Plesk guide"
elif [[ "$FLASK_ENV_MODE" == "development" ]]; then
    echo "  Local development:"
    echo "    bash run.sh          # start the development server"
    echo "    open http://localhost:5000"
else
    echo "  Production (Gunicorn):"
    echo "    source venv/bin/activate"
    echo "    gunicorn --bind 0.0.0.0:8000 --workers 2 wsgi:application"
    echo ""
    echo "  Or see DEPLOYMENT.md for Plesk/Passenger instructions."
fi
echo ""
echo "  Admin user (if not created above):"
echo "    flask create-user <username>"
echo ""
