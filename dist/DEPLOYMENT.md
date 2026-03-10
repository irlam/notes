# Deploying to Plesk

This guide covers deploying the Notes app to a Plesk-managed server using Passenger WSGI (Python).

## Prerequisites

- Plesk Obsidian or newer
- Python 3.8+ available on the server
- SSH access to the server
- A domain / subdomain configured in Plesk

---

## 1. Enable Python / Passenger in Plesk

1. Log in to Plesk.
2. Go to **Domains → yourdomain.com → Python**.
3. Set **Python version** to 3.8 or higher.
4. Set **Application root** to the directory where you will upload the app (e.g. `/var/www/vhosts/yourdomain.com/notes`).
5. Set **Application startup file** to `passenger_wsgi.py`.
6. Click **Apply**.

---

## 2. Upload the Application

Via SSH or Plesk File Manager, copy the project files to the application root:

```
notes/
├── app/
├── schema.sql
├── wsgi.py
├── passenger_wsgi.py
├── requirements.txt
└── ...
```

---

## 3. Create the Virtual Environment and Install Dependencies

SSH into the server and run:

```bash
cd /var/www/vhosts/yourdomain.com/notes
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

> **Important — platform-specific packages (Pillow, MarkupSafe)**
>
> Some dependencies in `requirements.txt` (notably **Pillow**) include compiled
> C extensions that are specific to the operating system and CPU architecture.
> You **must** run `pip install -r requirements.txt` on the **target Linux server**,
> not on a Windows or macOS machine.
>
> If you copy pre-installed packages from another machine (e.g. by committing or
> copying a `_pydeps` folder), the compiled `.pyd` / `.so` extension files will be
> wrong for the server's platform and Pillow will fail to import.  Symptoms include:
>
> ```
> {"error": "PDF generation failed",
>  "detail": "cannot import name '_imaging' from 'PIL' ..."}
> ```
>
> **Fix:** re-run `pip install -r requirements.txt` inside the venv on the server,
> or rebuild `_pydeps` on the server:
>
> ```bash
> pip install --target _pydeps -r requirements.txt
> ```

---

## 4. Configure Environment Variables

```bash
cp .env.example .env
nano .env   # or use any editor
```

Set at minimum:

```
SECRET_KEY=<a long random string>
DATABASE_PATH=/var/www/vhosts/yourdomain.com/notes/notes.db
FLASK_ENV=production
```

Generate a secret key with:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 5. Verify File Permissions

```bash
chmod 640 .env
chmod +x passenger_wsgi.py
```

Ensure the Plesk application user (e.g. `psacln`) can read the app files and write to the database path.

---

## 6. Restart the Application

In Plesk:
- Go to **Domains → yourdomain.com → Python**
- Click **Restart application**

Or via SSH:

```bash
touch passenger_wsgi.py   # triggers Passenger restart
```

---

## 7. Verify

Visit `https://yourdomain.com` — the Notes app should load.

Check the Plesk error log if something is wrong:

```
/var/www/vhosts/yourdomain.com/logs/error_log
```

---

## Updating the App

```bash
# Upload new files via SSH / git pull
cd /var/www/vhosts/yourdomain.com/notes
git pull origin main         # if using git

source venv/bin/activate
pip install -r requirements.txt
deactivate

touch passenger_wsgi.py      # restart Passenger
```

---

## Milestone 2: Notes CRUD & Status Columns

### Database Migration

Milestone 2 adds three new columns to the `notes` table (`is_pinned`, `is_archived`,
`is_trashed`). **Apply the migration before restarting the application** on an
existing database:

```bash
cd /var/www/vhosts/yourdomain.com/notes
source venv/bin/activate
python3 -c "
import sqlite3, os
db_path = os.environ.get('DATABASE_PATH', 'notes.db')
db = sqlite3.connect(db_path)
with open('migrations/002_add_note_status.sql') as f:
    db.executescript(f.read())
db.close()
print('Migration 002 applied.')
"
deactivate
```

Fresh installations (new `notes.db`) do **not** need to run this migration because
the updated `schema.sql` already includes the new columns.

### New API Endpoints (Milestone 2)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/notes?filter=active\|archived\|trashed` | List notes by status |
| `PUT` | `/api/notes/<id>` | Update title/body/is_pinned |
| `POST` | `/api/notes/<id>/archive` | Toggle archive status |
| `POST` | `/api/notes/<id>/restore` | Restore from trash |
| `DELETE` | `/api/notes/<id>` | Move note to trash (soft delete) |
| `DELETE` | `/api/notes/<id>/permanent` | Permanently delete (must be in trash) |

### Manual QA Checklist

- [ ] Create a note — appears in the active list
- [ ] Edit title and body — autosave indicator shows "Saving…" then "Saved" after ~1.5 s
- [ ] Pin a note — 📌 appears in the list and pinned note sorts to the top
- [ ] Unpin a note — returns to normal sort order
- [ ] Archive a note — disappears from active; visible under **Archived** tab
- [ ] Unarchive a note — returns to active list
- [ ] Trash a note — disappears from active; visible under **Trash** tab
- [ ] Restore from trash — returns to active list
- [ ] Permanently delete — note gone from trash; GET returns 404
- [ ] Offline banner appears when network is disconnected
- [ ] Mobile ≤ 767 px: sidebar shown first; tapping a note opens editor full-screen; back button returns to list
- [ ] Tablet / desktop: sidebar and editor visible side by side

### Edge Cases

- **Empty note created** — title and body blank; note is saved with defaults (handled)
- **Switch note while autosave pending** — pending save for previous note is flushed before opening next
- **Trashed note editor** — title and body are read-only; only Restore and Permanent Delete buttons shown
- **Archiving a trashed note** — returns 404 (not allowed)
- **Permanent delete of non-trashed note** — returns 404 (must trash first)
- **Data loss prevention** — back button flushes pending autosave immediately


| Issue | Solution |
|-------|----------|
| 500 error on first load | Check `error_log`; usually a missing dependency or wrong `DATABASE_PATH` |
| `ModuleNotFoundError: flask` | Re-run `pip install -r requirements.txt` inside the venv |
| Database permission error | Ensure the Plesk app user can write to the directory containing `notes.db` |
| `.env` not loaded | Confirm `.env` exists and is readable; `passenger_wsgi.py` loads it via `python-dotenv` |
| `RuntimeError: SECRET_KEY … must be set` | Set `SECRET_KEY` in `.env` to a random 32-byte hex string |

---

## Authentication & Session Configuration (Milestone 1)

### Create the first user

After deploying, SSH in and run:

```bash
cd /var/www/vhosts/yourdomain.com/notes
source venv/bin/activate
flask create-user admin
```

You will be prompted for a password (minimum 8 characters). The user is stored with
a bcrypt-compatible hash (`werkzeug.security.generate_password_hash`); the plain-text
password is never persisted.

### Cookie & session settings

Add the following to `.env` on the production server:

```
SECRET_KEY=<64-char hex secret>
SESSION_COOKIE_SECURE=true
SESSION_LIFETIME_DAYS=14
```

`SESSION_COOKIE_SECURE=true` prevents the session cookie from being sent over plain
HTTP. **This requires the domain to be served exclusively over HTTPS**, which Plesk
manages via Let's Encrypt.

`SESSION_COOKIE_HTTPONLY` is always `True` (hardcoded) — JavaScript cannot access
the session cookie.

`SESSION_COOKIE_SAMESITE` is always `Lax` — prevents CSRF for same-site navigation
while still allowing normal link clicks.

### Plesk: enforce HTTPS

1. In Plesk → **Domains → notes.defecttracker.uk → SSL/TLS Certificates**.
2. Issue a Let's Encrypt certificate.
3. Enable **Redirect from HTTP to HTTPS** in Plesk's hosting settings.
4. Confirm `SESSION_COOKIE_SECURE=true` is set in `.env` and restart the app.

### Rotating the secret key

Changing `SECRET_KEY` invalidates all existing sessions (users are logged out).
Generate a new key:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Update `.env`, then restart Passenger:

```bash
touch passenger_wsgi.py
```
