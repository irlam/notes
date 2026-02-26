# First-Time Install Guide

> **Deployment target:** notes.defecttracker.uk  
> **Hosting:** Plesk (Passenger WSGI, Python) — **no Docker, no containers**

This guide covers everything needed to get the app running from scratch, both
locally and on Plesk.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Local Development Setup](#2-local-development-setup)
3. [First Login — Create Your First User](#3-first-login--create-your-first-user)
4. [Running Tests](#4-running-tests)
5. [Plesk Deployment Setup](#5-plesk-deployment-setup)
6. [Database Bootstrap](#6-database-bootstrap)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Prerequisites

### Local development
- Python 3.8 or higher (`python3 --version`)
- `pip` (usually bundled with Python)
- Git

### Plesk server
- Plesk Obsidian or newer
- Python 3.8+ available on the server (no custom compilation needed)
- SSH access (or Plesk Terminal)
- A domain/subdomain configured in Plesk (e.g. `notes.defecttracker.uk`)

---

## 2. Local Development Setup

### 2a. Clone the repository

```bash
git clone <repo-url>
cd notes
```

### 2b. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate      # macOS / Linux
# .\venv\Scripts\Activate.ps1  # Windows PowerShell
```

### 2c. Install dependencies

```bash
pip install -r requirements.txt
```

### 2d. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and **set `SECRET_KEY` to a strong random value**:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# Copy the output and paste it as SECRET_KEY in .env
```

Leave all other values at their defaults for local development.

### 2e. Initialise the database

The database is created automatically on first startup using `schema.sql`.
Alternatively, use the bootstrap helper:

```bash
bash scripts/db_init.sh
```

### 2f. Start the development server

```bash
bash run.sh
```

Or, with the venv already active:

```bash
flask run --debug
```

Open http://localhost:5000 in your browser.

---

## 3. First Login — Create Your First User

The app requires authentication. After the database is initialised, create
your first user account:

```bash
source venv/bin/activate
flask create-user <username>
```

You will be prompted to enter and confirm a password (minimum 8 characters).

Then visit http://localhost:5000/login and sign in with the username and
password you just created.

> **Note:** There is no self-service registration; all users must be created
> via the CLI command. This is intentional for a personal/single-user app.

---

## 4. Running Tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

Tests use temporary SQLite databases and do not require any external services.
All 265 tests should pass.

To run a specific test file:

```bash
python -m pytest tests/test_notes.py -v
python -m pytest tests/test_milestone9.py -v
```

---

## 5. Plesk Deployment Setup

### 5a. Enable Python / Passenger in Plesk

1. Log in to Plesk.
2. Go to **Domains → notes.defecttracker.uk → Python**.
3. Set **Python version** to 3.8 or higher.
4. Set **Application root** to the directory where you will upload the app
   (e.g. `/var/www/vhosts/defecttracker.uk/notes.defecttracker.uk`).
5. Set **Application startup file** to `passenger_wsgi.py`.
6. Click **Apply**.

### 5b. Upload application files

Via SSH or Plesk File Manager, copy all project files (excluding `venv/`,
`*.db`, `uploads/`, and `.env`) to the application root.

### 5c. Create the virtual environment on the server

```bash
cd /var/www/vhosts/defecttracker.uk/notes.defecttracker.uk
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

### 5d. Configure the `.env` file on the server

```bash
cp .env.example .env
```

Edit `.env` with production values:

```
SECRET_KEY=<strong-random-32-hex-chars>
DATABASE_PATH=/var/www/vhosts/defecttracker.uk/notes.defecttracker.uk/notes.db
FLASK_ENV=production
SESSION_COOKIE_SECURE=true
SESSION_LIFETIME_DAYS=14
```

Set secure permissions:

```bash
chmod 640 .env
```

### 5e. Initialise the database

```bash
source venv/bin/activate
bash scripts/db_init.sh
deactivate
```

Or manually:

```bash
source venv/bin/activate
python3 -c "
import sqlite3, os
db_path = os.environ.get('DATABASE_PATH', 'notes.db')
db = sqlite3.connect(db_path)
with open('schema.sql') as f:
    db.executescript(f.read())
db.close()
print('Database initialised.')
"
deactivate
```

### 5f. Create your first user on the server

```bash
source venv/bin/activate
flask create-user <username>
deactivate
```

### 5g. Set up the uploads directory

```bash
mkdir -p uploads
chmod 750 uploads
```

Ensure the uploads directory is **not** accessible via the web. In Plesk, the
application root should be outside the web root, or configure a `.htaccess`
rule to deny access to `uploads/`.

### 5h. Static files permissions

```bash
chmod -R 755 app/static/
```

### 5i. Restart the Passenger application

```bash
touch passenger_wsgi.py
```

Plesk/Passenger detects the `passenger_wsgi.py` modification timestamp and
restarts the process automatically.

### 5j. HTTPS / SSL

1. In Plesk go to **Domains → notes.defecttracker.uk → SSL/TLS Certificates**.
2. Issue a **Let's Encrypt** certificate.
3. Enable **Redirect HTTP → HTTPS** in hosting settings.
4. Once HTTPS is active, set `SESSION_COOKIE_SECURE=true` in `.env` and
   restart Passenger (`touch passenger_wsgi.py`).

---

## 6. Database Bootstrap

### Fresh install (recommended)

Apply the canonical SQLite schema once:

```bash
source venv/bin/activate
bash scripts/db_init.sh
```

The script will:
- Check that `DATABASE_PATH` (or `notes.db`) does not already contain tables.
- Apply `schema.sql` to create all tables and indexes.
- Print confirmation when done.

For **MySQL 8+** production installs, use:

```sql
source db/schema.mysql.sql
```

### Existing install — applying migrations

If you already have a running database and need to apply schema changes from
a new version, apply the relevant migration files in order:

```bash
source venv/bin/activate
python3 -c "
import sqlite3, os
db = sqlite3.connect(os.environ.get('DATABASE_PATH', 'notes.db'))
with open('migrations/005_add_versions.sql') as f:
    db.executescript(f.read())
db.close()
print('Migration applied.')
"
```

See `migrations/README.md` for the full migration list.

### DEV-ONLY database reset

To completely wipe and rebuild the database during development:

```bash
bash scripts/db_reset_dev.sh
```

> ⚠️ **This destroys all data.** The script requires explicit typed confirmation
> before proceeding and will refuse to run if `FLASK_ENV=production`.

---

## 7. Troubleshooting

### `RuntimeError: SECRET_KEY environment variable must be set`

The app refuses to start without a strong `SECRET_KEY`. Copy `.env.example`
to `.env` and set `SECRET_KEY` to a random 32-hex-character string.

### App starts but login redirects loop

Ensure `SESSION_COOKIE_SECURE=false` in local dev (no HTTPS locally). On
production with HTTPS set it to `true`.

### Database not found

Check `DATABASE_PATH` in `.env` points to a writable location. On Plesk,
use an absolute path.

### Passenger doesn't pick up code changes

```bash
touch passenger_wsgi.py
```

### Upload fails with 413

The max upload size is 12 MB (10 MB image + multipart overhead). The
`MAX_CONTENT_LENGTH` is set in `app/__init__.py`.

### PDF export fails

Ensure `reportlab` and `Pillow` are installed in the venv:

```bash
source venv/bin/activate
pip show reportlab Pillow
```
