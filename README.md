# Notes

A clean, fast personal notes PWA hosted at **notes.defecttracker.uk**.  
Built with Python Flask (backend) and vanilla JS (frontend) — **no Docker, no containers**.

## Features

| Feature | Status |
|---|---|
| Authentication — login/logout, session management | ✅ Implemented |
| Two-pane layout (list + editor) | ✅ Implemented |
| Notes CRUD + autosave (1.5 s debounce) | ✅ Implemented |
| Folders + tags + full-text search | ✅ Implemented |
| Image upload + camera capture | ✅ Implemented |
| Image annotation (canvas drawing) | ✅ Implemented |
| Offline queue + sync status indicator | ✅ Implemented |
| PDF export (server-side, ReportLab) | ✅ Implemented |
| Version history + conflict copies | ✅ Implemented |
| PWA / installable (manifest + service worker) | ✅ Implemented |
| Settings page (change password, dark mode) | ✅ Implemented |
| Email PDF (direct email of note PDF) | 🔲 Planned — Milestone 10 |
| Batch export (ZIP / multi-note PDF) | 🔲 Planned — Milestone 10 |

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.8+, Flask 3 |
| Database | SQLite3 (raw, no ORM) |
| Frontend | Vanilla JS, HTML5, CSS3 |
| Hosting | Plesk (Passenger WSGI) — **no Docker** |
| Deployment target | notes.defecttracker.uk |

## Deployment

> **No Docker / no container-only workflows.**  
> The app runs directly on the Plesk server via Passenger WSGI (Python).

See [docs/first-install.md](docs/first-install.md) for the complete first-time install guide (local dev + Plesk).  
See [docs/deployment-notes.md](docs/deployment-notes.md) for the full Plesk deployment guide.

## Quick Start (local dev)

```bash
git clone <repo-url>
cd notes
bash run.sh
```

Then open http://localhost:5000 and log in (or create your first user — see below).

The script will:
1. Create a Python virtual environment (`venv/`)
2. Install dependencies from `requirements.txt`
3. Copy `.env.example` → `.env` if no `.env` exists
4. Initialise the SQLite database from `schema.sql`
5. Start Flask dev server on port 5000

### Create your first user

After starting the app for the first time, create an admin/user account:

```bash
source venv/bin/activate
flask create-user <username>
```

You will be prompted for a password (minimum 8 characters). Then log in at http://localhost:5000/login.

## Project Structure

```
notes/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── auth.py              # Login/logout + login_required decorator
│   ├── database.py          # SQLite helpers
│   ├── email_export.py      # M10 stubs: email PDF + batch export (501 placeholders)
│   ├── media.py             # Image upload, camera, annotation
│   ├── pdf.py               # PDF export (ReportLab)
│   ├── routes.py            # Notes API + dashboard + sync
│   ├── settings.py          # Settings page + change-password
│   ├── versions.py          # Version history + conflict copies
│   ├── static/
│   │   ├── css/style.css
│   │   ├── js/app.js
│   │   ├── js/annotation.js
│   │   ├── icons/           # PWA icons
│   │   ├── manifest.json
│   │   └── sw.js            # Service worker
│   └── templates/
│       ├── dashboard.html
│       ├── login.html
│       └── settings.html
├── db/
│   └── schema.mysql.sql     # Canonical MySQL 8+ schema for fresh production installs
├── docs/                    # Project documentation
│   ├── first-install.md     # ← First-time install guide (local + Plesk)
│   ├── milestone-10.md      # ← M10 planning: Email PDF + Batch Export
│   ├── milestones.md        # Milestone plan with status matrix
│   ├── architecture.md
│   ├── product-spec.md
│   ├── release-checklist.md
│   ├── deployment-notes.md
│   ├── security-checklist.md
│   └── qa-checklists/
│       └── README.md
├── migrations/              # SQL migration files (applied to existing installs)
├── scripts/
│   ├── db_init.sh           # Bootstrap helper — safe, non-destructive
│   └── db_reset_dev.sh      # DEV-ONLY reset (requires confirmation)
├── schema.sql               # Canonical SQLite schema (fresh install)
├── wsgi.py                  # WSGI entry (local / gunicorn)
├── passenger_wsgi.py        # Plesk Passenger entry
├── requirements.txt
├── run.sh                   # Local dev runner
├── .env.example
├── CHANGELOG.md
└── DEPLOYMENT.md
```

## Environment Variables

Copy `.env.example` to `.env` and customise:

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(required)* | Flask session secret — generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_PATH` | `notes.db` | Path to SQLite database file |
| `FLASK_ENV` | `production` | `development` enables debug mode |
| `SESSION_COOKIE_SECURE` | `false` | Set `true` in production (HTTPS required) |
| `SESSION_LIFETIME_DAYS` | `14` | Session cookie lifetime in days |
| `ENABLE_EMAIL_EXPORT` | `false` | Enable Milestone 10 email PDF feature (not yet implemented) |
| `SMTP_HOST` | *(empty)* | SMTP server hostname (M10) |
| `SMTP_PORT` | `587` | SMTP port (M10) |
| `SMTP_USER` | *(empty)* | SMTP username (M10) |
| `SMTP_PASS` | *(empty)* | SMTP password (M10) |
| `SMTP_FROM` | *(empty)* | From address for outbound email (M10) |

## API Reference

| Method | Path | Description |
|---|---|---|
| GET | `/api/notes` | List notes (supports `filter`, `q`, `folder_id`, `tag_id`, `sort`) |
| POST | `/api/notes` | Create a note |
| GET | `/api/notes/<id>` | Get a single note |
| PUT | `/api/notes/<id>` | Update a note (conflict detection via `client_updated_at`) |
| DELETE | `/api/notes/<id>` | Move note to trash (or permanently delete if already trashed) |
| GET | `/api/notes/<id>/export.pdf` | Export note to PDF |
| GET | `/api/notes/<id>/versions` | List version history |
| POST | `/api/notes/<id>/versions/<vid>/restore` | Restore a version |
| GET | `/api/conflicts` | List conflict copies |
| DELETE | `/api/conflicts/<id>` | Delete a conflict copy |
| POST | `/api/sync` | Bulk offline sync |
| GET/POST/DELETE | `/api/folders` | Folder management |
| GET/POST/DELETE | `/api/tags` | Tag management |
| POST | `/api/notes/<id>/images` | Upload image |
| PUT | `/api/notes/<id>/images/<img_id>` | Update annotation data |
| DELETE | `/api/notes/<id>/images/<img_id>` | Delete image |
| POST | `/api/notes/<id>/email-pdf` | **[M10 stub — 501]** Email PDF |
| POST | `/api/batch-export` | **[M10 stub — 501]** Batch export |

All endpoints require authentication and return JSON. DELETE returns 204 No Content.

## Testing

```bash
python -m pytest tests/ -v
```

Requires `requirements.txt` dependencies installed. Uses SQLite in-memory/tmp databases — no external services needed. See [docs/first-install.md](docs/first-install.md) for full test setup instructions.

## Documentation Index

| Document | Purpose |
|---|---|
| [docs/first-install.md](docs/first-install.md) | First-time install guide (local dev + Plesk) |
| [docs/milestone-10.md](docs/milestone-10.md) | Milestone 10 planning: Email PDF + Batch Export |
| [docs/architecture.md](docs/architecture.md) | System architecture (frontend, backend, storage, sync) |
| [docs/product-spec.md](docs/product-spec.md) | Full feature specification |
| [docs/milestones.md](docs/milestones.md) | Milestones & acceptance criteria with status matrix |
| [docs/ui-screens.md](docs/ui-screens.md) | UI screen inventory & wireframe notes |
| [docs/data-model.md](docs/data-model.md) | Database schema & data decisions |
| [docs/sync-strategy.md](docs/sync-strategy.md) | Autosave, offline & sync-status design |
| [docs/security-checklist.md](docs/security-checklist.md) | Security review checklist |
| [docs/deployment-notes.md](docs/deployment-notes.md) | Plesk deployment, backup & logging (no Docker) |
| [docs/release-checklist.md](docs/release-checklist.md) | Pre-go-live release checklist |
| [docs/versioning.md](docs/versioning.md) | Version history model and conflict UX |
| [docs/qa-checklists/README.md](docs/qa-checklists/README.md) | Manual QA checklists |
| [CHANGELOG.md](CHANGELOG.md) | Version history |