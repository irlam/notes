# Deployment Notes — Notes PWA (Plesk)

> **Deployment target:** notes.defecttracker.uk  
> **Hosting:** Plesk (Passenger WSGI, Python) — **no Docker / no containers**  
> This document supersedes the legacy `DEPLOYMENT.md` in the repository root.

---

## Prerequisites

| Requirement | Details |
|---|---|
| Plesk version | Obsidian or newer |
| Python version | 3.8 or higher (available on the server) |
| SSH access | Required for venv setup and git operations |
| Domain | `notes.defecttracker.uk` configured as a subdomain in Plesk |
| SSL | Let's Encrypt certificate enabled for the subdomain |

---

## 1. Create / Configure the Subdomain in Plesk

1. Log in to Plesk.
2. Go to **Domains → Add Subdomain**.
3. Enter `notes` under `defecttracker.uk`.
4. Set the document root to a suitable path, e.g.  
   `/var/www/vhosts/defecttracker.uk/notes.defecttracker.uk`
5. Enable **Let's Encrypt SSL** for the subdomain.
6. Enable HTTP → HTTPS redirect.

---

## 2. Enable Python / Passenger in Plesk

1. Go to **Domains → notes.defecttracker.uk → Python**.
2. Set **Python version** to 3.8 or higher.
3. Set **Application root** to the directory where the app files will live, e.g.  
   `/var/www/vhosts/defecttracker.uk/notes.defecttracker.uk/app_root`
4. Set **Application startup file** to `passenger_wsgi.py`.
5. Set **Application URL** to `/`.
6. Click **Apply**.

---

## 3. Deploy the Application Files

SSH into the server and clone (or upload) the repository:

```bash
cd /var/www/vhosts/defecttracker.uk/notes.defecttracker.uk/
git clone <repo-url> app_root
cd app_root
```

Or use the Plesk **File Manager** / **Git** extension to pull the repository.

---

## 4. Create the Virtual Environment and Install Dependencies

```bash
cd /var/www/vhosts/defecttracker.uk/notes.defecttracker.uk/app_root
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

> **No Docker.** All dependencies are installed directly into the `venv/` directory on the host.

---

## 5. Configure Environment Variables

```bash
cp .env.example .env
nano .env
```

Set at minimum:

```ini
SECRET_KEY=<a cryptographically random string — 32+ hex chars>
DATABASE_PATH=/var/www/vhosts/defecttracker.uk/notes.defecttracker.uk/app_root/notes.db
FLASK_ENV=production
```

Generate a secret key:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 6. Set File Permissions

```bash
chmod 640 .env
chmod +x passenger_wsgi.py
```

Ensure the Plesk application user (typically `psacln`) can read the app files and write to the directory containing `notes.db`:

```bash
chown -R <plesk-user>:psaserv /var/www/vhosts/defecttracker.uk/notes.defecttracker.uk/app_root
```

---

## 7. Initialise the Database

The database is initialised automatically on first request (the app factory calls `init_db()`). Alternatively, initialise manually:

```bash
source venv/bin/activate
python3 -c "from app import create_app; create_app()"
deactivate
```

This creates `notes.db` at the path specified in `DATABASE_PATH`.

---

## 8. Restart the Application

In Plesk:
- Go to **Domains → notes.defecttracker.uk → Python**
- Click **Restart application**

Or via SSH:

```bash
touch /var/www/vhosts/defecttracker.uk/notes.defecttracker.uk/app_root/passenger_wsgi.py
```

Passenger watches the startup file's modification time and restarts the app when it changes.

---

## 9. Verify the Deployment

1. Visit https://notes.defecttracker.uk — the Notes app should load.
2. Create and save a note; confirm it persists on page reload.
3. Check the PWA install prompt appears in the browser.
4. Open browser DevTools → Application → Service Workers; confirm the service worker is registered.

Check the Plesk error log if something is wrong:

```
/var/www/vhosts/defecttracker.uk/logs/error_log
```

---

## 10. Updating the App

```bash
cd /var/www/vhosts/defecttracker.uk/notes.defecttracker.uk/app_root
git pull origin main

source venv/bin/activate
pip install -r requirements.txt
deactivate

touch passenger_wsgi.py   # triggers Passenger restart
```

If the database schema has changed, apply the migration:

```bash
source venv/bin/activate
python3 -c "
import sqlite3, os
db = sqlite3.connect(os.environ.get('DATABASE_PATH', 'notes.db'))
with open('migrations/NNN_description.sql') as f:
    db.executescript(f.read())
db.close()
"
deactivate
```

---

## 11. Rollback

```bash
cd /var/www/vhosts/defecttracker.uk/notes.defecttracker.uk/app_root
git log --oneline -10          # find the previous good commit
git checkout <commit-sha>
touch passenger_wsgi.py
```

Restore the database from backup if schema changes were applied:

```bash
cp notes.db.backup notes.db
```

> **Best practice:** Take a copy of `notes.db` before every deployment.

---

## 12. Troubleshooting

| Issue | Solution |
|---|---|
| 500 error on first load | Check `error_log`; usually a missing dependency or wrong `DATABASE_PATH` |
| `ModuleNotFoundError: flask` | Re-run `pip install -r requirements.txt` inside the venv |
| Database permission error | Ensure the Plesk app user can write to the directory containing `notes.db` |
| `.env` not loaded | Confirm `.env` exists and is readable; `passenger_wsgi.py` loads it via `python-dotenv` |
| Service worker not updating | Bump the cache version in `sw.js` and redeploy |
| App not restarting after `touch` | Check Passenger is enabled for the domain in Plesk; try clicking Restart in the UI |

---

## 13. Backup Strategy

### Database Backup

The SQLite database (`notes.db`) is a single file on the Plesk server filesystem. Back it up regularly using one of the following approaches:

**Manual / scripted copy (recommended minimum)**

```bash
# Run from the app root directory
cp notes.db "notes.db.$(date +%Y%m%d-%H%M%S).backup"
```

Take a copy before every deployment (see §10 Updating the App).

**Plesk Scheduled Tasks (Cron)**

Use Plesk → **Scheduled Tasks** to run a nightly backup script:

```bash
#!/bin/bash
APP_ROOT="/var/www/vhosts/defecttracker.uk/notes.defecttracker.uk/app_root"
BACKUP_DIR="/var/www/vhosts/defecttracker.uk/backups/notes"
mkdir -p "$BACKUP_DIR"
cp "$APP_ROOT/notes.db" "$BACKUP_DIR/notes.db.$(date +%Y%m%d).backup"
# Keep only the last 14 daily backups
find "$BACKUP_DIR" -name '*.backup' -mtime +14 -delete
```

Store the `BACKUP_DIR` outside the web root so backups are not web-accessible.

**Plesk Backup Manager**

Plesk's built-in **Backup Manager** (Domains → Backup Manager) can back up the entire domain including files. Schedule full domain backups weekly and incremental backups daily. Confirm that the domain backup includes the app root directory where `notes.db` lives.

### Media Files Backup (Milestone 3+)

When image attachments are added (M3), media files will be stored under `uploads/` (excluded from git via `.gitignore`). Include this directory in the nightly backup script:

```bash
tar -czf "$BACKUP_DIR/uploads.$(date +%Y%m%d).tar.gz" "$APP_ROOT/uploads/"
```

### Restore

To restore the database from a backup:

```bash
cp notes.db notes.db.pre-restore   # keep a copy of the broken db just in case
cp /path/to/backup/notes.db.YYYYMMDD.backup notes.db
touch passenger_wsgi.py            # restart Passenger to pick up the restored file
```

### Backup Checklist

- [ ] Daily automated backup of `notes.db` configured in Plesk Scheduled Tasks.
- [ ] Backup directory is outside the web root.
- [ ] Retention policy applied (e.g. keep 14 daily backups).
- [ ] Backup restored and verified at least once after initial setup.
- [ ] Plesk Backup Manager schedule confirmed.

---

## 14. Logging & Diagnostics

### Application Logs (Passenger / Plesk)

Passenger writes Flask stdout/stderr to the domain error log:

```
/var/www/vhosts/defecttracker.uk/logs/error_log
```

View the last 100 lines:

```bash
tail -100 /var/www/vhosts/defecttracker.uk/logs/error_log
```

Watch in real time:

```bash
tail -f /var/www/vhosts/defecttracker.uk/logs/error_log
```

### Access Logs

HTTP access logs (request method, path, status code, response time) are in:

```
/var/www/vhosts/defecttracker.uk/logs/access_log
```

Useful for diagnosing 4xx/5xx rates or slow requests:

```bash
grep ' 500 ' /var/www/vhosts/defecttracker.uk/logs/access_log | tail -50
```

### Flask Application Logging

Flask's built-in logger writes to stderr (captured by Passenger → error_log).  
Log level is controlled by `FLASK_ENV`:

| `FLASK_ENV` | Log level | Debug toolbar |
|---|---|---|
| `production` | WARNING | Off |
| `development` | DEBUG | On (local only) |

To add diagnostic logging in `routes.py` or `database.py`:

```python
import logging
logger = logging.getLogger(__name__)
logger.warning("Something unexpected: %s", detail)
```

Avoid logging sensitive data (note content, secrets, full request bodies).

### Diagnosing a 500 Error

1. Check `error_log` for the Python traceback.
2. Confirm `DATABASE_PATH` in `.env` points to a writable location.
3. Confirm the venv is activated and `flask` is importable:
   ```bash
   source venv/bin/activate && python3 -c "import flask; print(flask.__version__)"
   ```
4. Confirm `FLASK_ENV=production` (debug mode must be off in production).
5. Restart Passenger: `touch passenger_wsgi.py`.

### Diagnosing a Service Worker Issue

1. Open browser DevTools → **Application** → **Service Workers**.
2. Confirm the SW is registered and active.
3. If the SW is stuck on "waiting to activate": click **skipWaiting** in DevTools, or bump the cache version in `sw.js` and redeploy.
4. Clear site data (DevTools → Application → Clear storage) to force a fresh install.

### Plesk Log Viewer

Plesk provides a web-based log viewer:  
**Domains → notes.defecttracker.uk → Logs**

This is useful when SSH access is not available.

---

## 15. Not Supported

- **Docker / containers** — not used; not supported.  
- **Gunicorn as a standalone server in production** — use Passenger WSGI via Plesk only.  
- **Systemd service files** — Passenger manages the process lifecycle.

---

## 16. Milestone 8 — Hardening Deployment Notes

### HTTP Security Headers

All HTTP responses now include security headers set in the Flask app factory
(`app/__init__.py`). No additional Plesk / Apache configuration is required for
these headers, but the following additional server-level header is **strongly
recommended** and should be added in Plesk → **Apache & nginx Settings** →
**Additional directives for HTTPS**:

```apache
Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
```

This adds HSTS (HTTP Strict Transport Security), which forces browsers to
always use HTTPS for the domain. **Only add this after confirming HTTPS works
correctly** — once HSTS is active, HTTP access is blocked by browsers.

### Applying the M8 Update

```bash
cd /var/www/vhosts/defecttracker.uk/notes.defecttracker.uk/app_root

# Back up the database before updating
cp notes.db "notes.db.$(date +%Y%m%d-%H%M%S).backup"

git pull origin main

source venv/bin/activate
pip install -r requirements.txt
deactivate

touch passenger_wsgi.py   # restart Passenger
```

No database migrations are required for M8.

### Settings Page

The new `/settings` page is accessible from the sidebar footer (⚙️). It
provides:
- Username display
- Change password form (requires the current password)
- Dark mode toggle (stored in `localStorage`, no server round-trip)

### Verifying Security Headers in Production

After deploying, verify the headers are set:

```bash
curl -sI https://notes.defecttracker.uk | grep -E 'X-Frame|X-Content|Referrer|Permissions|Content-Security'
```

Expected output should include:
```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
Content-Security-Policy: default-src 'self'; ...
```

### Rate-Limiting on the Login Endpoint

Flask-level rate limiting is not included (to avoid adding dependencies).
For production, apply rate limiting at the Apache level via Plesk:

In Plesk → **Apache & nginx Settings** → **Additional directives for HTTP/HTTPS**:

```apache
<Location /login>
    # Limit to 10 requests per second per IP (requires mod_ratelimit)
    SetOutputFilter RATE_LIMIT
    SetEnv rate-limit 10
</Location>
```

Alternatively, contact the hosting provider to enable `mod_evasive` or
`mod_security` at the server level.
