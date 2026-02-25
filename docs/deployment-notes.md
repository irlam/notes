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

## 13. Not Supported

- **Docker / containers** — not used; not supported.  
- **Gunicorn as a standalone server in production** — use Passenger WSGI via Plesk only.  
- **Systemd service files** — Passenger manages the process lifecycle.
