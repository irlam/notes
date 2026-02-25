# Notes

A clean, fast personal notes PWA hosted at **notes.defecttracker.uk**.  
Built with Python Flask (backend) and vanilla JS (frontend) — **no Docker, no containers**.

## Vision

Single-user-first, multi-user-ready note-taking app with autosave, offline resilience, image annotation, PDF export, and real-time sync-status feedback. Installable on any device as a Progressive Web App.

## Planned Features

| Feature | Status |
|---|---|
| Two-pane layout (list + editor) | ✅ Implemented |
| Autosave (1.5 s debounce) | ✅ Implemented |
| PWA / installable | ✅ Implemented |
| Offline indicator | ✅ Implemented |
| Touch-friendly (44 px targets) | ✅ Implemented |
| Delete confirmation | ✅ Implemented |
| Sync status indicator | 🔲 Planned |
| Image annotation | 🔲 Planned |
| PDF export | 🔲 Planned |
| Rich-text / Markdown editing | 🔲 Planned |
| Multi-user / auth | 🔲 Future milestone |

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

See [docs/deployment-notes.md](docs/deployment-notes.md) for the full Plesk deployment guide.

## Quick Start (local dev)

```bash
git clone <repo-url>
cd notes
bash run.sh
```

Then open http://localhost:5000.

The script will:
1. Create a Python virtual environment (`venv/`)
2. Install dependencies from `requirements.txt`
3. Copy `.env.example` → `.env` if no `.env` exists
4. Start Flask dev server on port 5000

## Project Structure

```
notes/
├── app/
│   ├── __init__.py        # Flask app factory
│   ├── database.py        # SQLite helpers
│   ├── routes.py          # API + page routes
│   ├── static/
│   │   ├── css/style.css
│   │   ├── js/app.js
│   │   ├── icons/         # PWA icons
│   │   ├── manifest.json
│   │   └── sw.js          # Service worker
│   └── templates/
│       └── index.html
├── docs/                  # Project documentation
│   ├── architecture.md    # System architecture overview
│   ├── product-spec.md
│   ├── milestones.md
│   ├── ui-screens.md
│   ├── data-model.md
│   ├── sync-strategy.md
│   ├── security-checklist.md
│   ├── deployment-notes.md
│   └── qa-checklists/
│       └── README.md
├── migrations/            # SQL migration files (applied after initial schema.sql)
├── schema.sql             # DB schema
├── wsgi.py                # WSGI entry (local / gunicorn)
├── passenger_wsgi.py      # Plesk Passenger entry
├── requirements.txt
├── run.sh                 # Local dev runner
├── .env.example
├── CHANGELOG.md
└── DEPLOYMENT.md          # Legacy — superseded by docs/deployment-notes.md
```

## Environment Variables

Copy `.env.example` to `.env` and customise:

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `change-me-…` | Flask session secret (required) |
| `DATABASE_PATH` | `notes.db` | Path to SQLite database file |
| `FLASK_ENV` | `production` | `development` enables debug |

## API Reference

| Method | Path | Description |
|---|---|---|
| GET | `/api/notes` | List all notes |
| POST | `/api/notes` | Create a note |
| GET | `/api/notes/<id>` | Get a single note |
| PUT | `/api/notes/<id>` | Update a note |
| DELETE | `/api/notes/<id>` | Delete a note |

All endpoints return JSON. DELETE returns 204 No Content.

## Documentation Index

| Document | Purpose |
|---|---|
| [docs/architecture.md](docs/architecture.md) | System architecture (frontend, backend, storage, sync) |
| [docs/product-spec.md](docs/product-spec.md) | Full feature specification |
| [docs/milestones.md](docs/milestones.md) | Milestones & acceptance criteria |
| [docs/ui-screens.md](docs/ui-screens.md) | UI screen inventory & wireframe notes |
| [docs/data-model.md](docs/data-model.md) | Database schema & data decisions |
| [docs/sync-strategy.md](docs/sync-strategy.md) | Autosave, offline & sync-status design |
| [docs/security-checklist.md](docs/security-checklist.md) | Security review checklist |
| [docs/deployment-notes.md](docs/deployment-notes.md) | Plesk deployment, backup & logging (no Docker) |
| [docs/qa-checklists/README.md](docs/qa-checklists/README.md) | Manual QA checklist structure |
| [CHANGELOG.md](CHANGELOG.md) | Version history |