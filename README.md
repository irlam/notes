# Notes

A clean, fast personal notes web app with a Samsung Notes-style two-pane layout. Built with Python Flask (backend) and vanilla JS (frontend). Installable as a PWA.

## Features

- **Two-pane layout** — note list on the left, editor on the right
- **Autosave** — changes saved automatically after 1.5 s of inactivity
- **PWA** — installable, works offline (app shell cached via service worker)
- **Touch-friendly** — responsive, minimum 44 px tap targets
- **Delete confirmation** — no accidental data loss
- **Offline indicator** — banner shown when network is unavailable

## Tech Stack

| Layer    | Technology                     |
|----------|-------------------------------|
| Backend  | Python 3.8+, Flask 3           |
| Database | SQLite3 (raw, no ORM)          |
| Frontend | Vanilla JS, HTML5, CSS3        |
| Hosting  | Plesk (Passenger WSGI) or any  |

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
│   │   ├── icons/         # PWA icons (add your own)
│   │   ├── manifest.json
│   │   └── sw.js          # Service worker
│   └── templates/
│       └── index.html
├── schema.sql             # DB schema
├── wsgi.py                # WSGI entry (local / gunicorn)
├── passenger_wsgi.py      # Plesk Passenger entry
├── requirements.txt
├── run.sh                 # Local dev runner
├── .env.example
└── DEPLOYMENT.md
```

## Environment Variables

Copy `.env.example` to `.env` and customise:

| Variable        | Default                   | Description                     |
|-----------------|---------------------------|---------------------------------|
| `SECRET_KEY`    | `change-me-…`             | Flask session secret (required) |
| `DATABASE_PATH` | `notes.db`                | Path to SQLite database file    |
| `FLASK_ENV`     | `production`              | `development` enables debug     |

## API Reference

| Method | Path                  | Description         |
|--------|-----------------------|---------------------|
| GET    | `/api/notes`          | List all notes      |
| POST   | `/api/notes`          | Create a note       |
| GET    | `/api/notes/<id>`     | Get a single note   |
| PUT    | `/api/notes/<id>`     | Update a note       |
| DELETE | `/api/notes/<id>`     | Delete a note       |

All endpoints return JSON. DELETE returns 204 No Content.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for Plesk deployment instructions.