# Architecture — Notes PWA

> **Deployment target:** notes.defecttracker.uk  
> **Hosting:** Plesk (Passenger WSGI, Python) — **no Docker / no containers**

---

## 1. System Overview

The Notes PWA is a single-page application with a thin Python/Flask backend.  
All persistence is handled server-side via SQLite; offline resilience is handled client-side via the service worker and (from Milestone 2) an IndexedDB write queue.

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                             │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Vanilla JS SPA  (app.js)                          │    │
│  │  ┌─────────────────┐   ┌───────────────────────┐  │    │
│  │  │  Note List Pane  │   │  Note Editor Pane     │  │    │
│  │  └─────────────────┘   └───────────────────────┘  │    │
│  │                                                     │    │
│  │  fetch() ──► REST API  /api/notes/*                 │    │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │ (HTTPS)                               │
│  ┌──────────────────▼──────────────────────────────────┐   │
│  │  Service Worker  (sw.js)                             │   │
│  │  • Cache-first  → app shell (HTML/CSS/JS/icons)      │   │
│  │  • Network-first → API calls                         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │ HTTPS / Passenger WSGI
┌─────────────────────────▼───────────────────────────────────┐
│                    Plesk Server                              │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Python 3.8+ / Flask 3   (passenger_wsgi.py)       │    │
│  │  ┌──────────────┐  ┌──────────────┐               │    │
│  │  │  routes.py   │  │  database.py  │               │    │
│  │  └──────────────┘  └──────┬───────┘               │    │
│  └─────────────────────────  │  ────────────────────── │    │
│                               │                         │    │
│  ┌────────────────────────────▼────────────────────┐   │    │
│  │  SQLite  (notes.db — filesystem, no Docker)      │   │    │
│  └──────────────────────────────────────────────────┘   │    │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Frontend Architecture

### Technology

| Concern | Approach |
|---|---|
| Framework | None — vanilla JavaScript (ES2020+) |
| HTML | Single template rendered by Flask (`templates/index.html`) |
| CSS | Single stylesheet (`static/css/style.css`) |
| JavaScript | Single module (`static/js/app.js`) |
| PWA | `manifest.json` + service worker (`static/sw.js`) |

### Responsibilities

- **Rendering:** The server renders `index.html` once; all subsequent UI updates are DOM mutations via JavaScript.
- **Data fetching:** All note data is loaded via `fetch()` against the `/api/notes/*` endpoints.
- **Autosave:** A 1.5 s debounce on the editor's `input` event fires a `PUT` request.
- **Offline detection:** `navigator.onLine` + `window` `online`/`offline` events toggle an offline banner.
- **PWA install:** The `beforeinstallprompt` event is captured and surfaced as an "Install app" button.

### File Layout

```
app/static/
├── css/style.css        # All styles; CSS custom properties for design tokens
├── js/app.js            # Single-file SPA logic (no bundler required)
├── icons/               # PWA icons (multiple sizes)
├── manifest.json        # Web App Manifest
└── sw.js                # Service worker
app/templates/
└── index.html           # Shell HTML; loaded once; inlines the manifest link
```

### Progressive Web App Strategy

The app is PWA-first: installable on all major platforms via the browser "Add to home screen" mechanism.

| PWA Requirement | Implementation |
|---|---|
| HTTPS | Enforced via Plesk Let's Encrypt |
| Web App Manifest | `manifest.json` — name, icons, `display: standalone`, `start_url: /` |
| Service Worker | `sw.js` — registered from `index.html`; caches app shell on install |
| Offline support | App shell served from cache; API gracefully degrades offline |
| Responsive layout | Two-pane desktop, single-pane mobile (CSS `@media` breakpoints) |

---

## 3. Backend Architecture

### Technology

| Concern | Approach |
|---|---|
| Language | Python 3.8+ |
| Framework | Flask 3 (micro-framework; no ORM) |
| WSGI server | Phusion Passenger (via Plesk) — `passenger_wsgi.py` |
| Local dev server | Flask built-in dev server — `run.sh` starts `flask run` |
| Configuration | `python-dotenv` loads `.env`; no secrets in source |

### Application Structure

```
app/
├── __init__.py     # App factory (create_app); loads config, inits DB
├── database.py     # SQLite connection helpers (get_db, init_db, close_db)
├── routes.py       # All HTTP routes: page + REST API
```

### Request Lifecycle

```
Browser request
  → Passenger WSGI (passenger_wsgi.py)
    → Flask app factory (create_app)
      → Blueprint routes (routes.py)
        → SQLite via get_db() (database.py)
          → JSON / HTML response
```

### REST API Surface

| Method | Path | Action |
|---|---|---|
| GET | `/` | Serve the SPA shell |
| GET | `/api/notes` | List all notes for current user |
| POST | `/api/notes` | Create a note |
| GET | `/api/notes/<id>` | Get a single note |
| PUT | `/api/notes/<id>` | Update a note |
| DELETE | `/api/notes/<id>` | Delete a note (204) |

All API endpoints return `application/json`.  
All state-changing requests use parameterised SQL (no string interpolation).

### Configuration Strategy

Configuration is loaded from environment variables only (never hard-coded):

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Flask session secret; must be ≥ 32 random hex chars |
| `DATABASE_PATH` | No | Absolute path to `notes.db`; defaults to repo root |
| `FLASK_ENV` | No | `production` (default) disables debug mode |

`.env.example` documents all variables without revealing values.  
`.env` is listed in `.gitignore` — never committed.

---

## 4. Storage Architecture

### SQLite

| Property | Detail |
|---|---|
| Engine | SQLite 3 (built into Python) |
| Location | Filesystem path set by `DATABASE_PATH` in `.env` |
| Access | Raw SQL via `sqlite3` stdlib; no ORM |
| Schema | `schema.sql` — applied once on first `create_app()` call |
| Multi-user readiness | `user_id` column on all user-owned tables (defaults to `1` in v1) |

Current schema:

```sql
CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER  PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER  NOT NULL DEFAULT 1,
    title       TEXT     NOT NULL DEFAULT '',
    body        TEXT     NOT NULL DEFAULT '',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes (user_id);
```

### Media Files (Milestone 3+)

Media attachments (images) will be stored on the server filesystem (not as SQLite BLOBs).  
The storage path will be outside the web root and served via a dedicated Flask endpoint.  
See [data-model.md](data-model.md) for the planned `media` table schema.

### Client-Side Storage (Milestone 2+)

| Store | Technology | Purpose |
|---|---|---|
| Offline write queue | IndexedDB | Pending PUT/POST/DELETE requests when offline |
| App shell cache | Service Worker Cache API | HTML, CSS, JS, icons — served offline |

---

## 5. Sync Strategy Overview

Full detail in [sync-strategy.md](sync-strategy.md). Summary:

### Current (Milestone 1)

- **Autosave:** Editor debounces `input` → `PUT /api/notes/<id>` after 1.5 s of inactivity.
- **Offline caching:** Service worker caches the app shell (HTML/CSS/JS) using cache-first strategy. API calls use network-first; failure while offline returns an error without crashing the app.
- **No write queue:** Edits made while offline are lost in v1. (Fixed in Milestone 2.)

### Planned (Milestone 2)

- **IndexedDB write queue:** Offline edits are queued in the browser; flushed on `online` event.
- **Sync status chip:** UI shows `Saved ✓` / `Saving…` / `Unsaved changes` / `Error ✗`.
- **Retry with back-off:** Failed syncs retry with exponential back-off (2 s → 60 s cap).
- **Conflict resolution:** Last-write-wins based on `updated_at` timestamp (v1).

---

## 6. Deployment Architecture

```
Internet ──HTTPS──► Plesk (Apache/Nginx proxy)
                       └──► Passenger WSGI
                               └──► Python venv
                                       └──► Flask app (passenger_wsgi.py)
                                               └──► SQLite (notes.db)
```

| Layer | Technology | Notes |
|---|---|---|
| TLS termination | Plesk / Let's Encrypt | Auto-renewed; HTTPS enforced |
| Reverse proxy | Plesk-managed Apache or Nginx | Passenger integration |
| Application server | Phusion Passenger | Manages Python process lifecycle |
| Application | Flask 3 (Python 3.8+) | Loaded via `passenger_wsgi.py` |
| Database | SQLite on host filesystem | No separate DB server required |
| Dependencies | Python virtualenv (`venv/`) | Installed on the host, not in a container |

**No Docker. No containers. No root access required beyond standard Plesk domain management.**

See [deployment-notes.md](deployment-notes.md) for the full step-by-step Plesk deployment guide.

---

## 7. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Frontend framework | None (vanilla JS) | Minimises dependencies; no build step required; works on shared hosting |
| Backend framework | Flask (micro) | Lightweight; no ORM coupling; easy to deploy via Passenger WSGI |
| Database | SQLite | Zero-config; sufficient for single-user; already on the server |
| No ORM | Raw SQL | Reduces dependencies; predictable query behaviour on SQLite |
| No Docker | Host venv | Plesk shared hosting; no container runtime available |
| PWA-first | Manifest + SW | Installable on mobile without an app store; offline support built in |
| Single-user v1 | `user_id = 1` default | Fastest path to working app; schema is multi-user-ready for later |

---

## 8. Open Architecture Decisions

| # | Question | Status |
|---|---|---|
| OD-1 | Offline queue storage: IndexedDB vs localStorage | **IndexedDB** (confirmed for M2) |
| OD-2 | Rich-text format in DB: HTML vs Markdown vs Delta | **TBD (M3)** |
| OD-3 | Image storage: filesystem path vs SQLite BLOB | **Filesystem preferred (M3)** |
| OD-4 | PDF export: `window.print()` vs jsPDF vs Puppeteer | **TBD (M3)** |
| OD-5 | Annotation persistence: SVG overlay vs merged PNG | **TBD (M3)** |
| OD-6 | Multi-user auth trigger: after M3 or after M4? | **TBD** |
