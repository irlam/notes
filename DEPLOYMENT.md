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

## Troubleshooting

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
