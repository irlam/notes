# Milestones — Notes PWA

> **Deployment target:** notes.defecttracker.uk  
> **Hosting:** Plesk / Passenger WSGI — no Docker

---

## Milestone 0 — Project Foundation & Architecture (complete)

**Goal:** Establish project structure, conventions, and documentation before any feature implementation.  
No new user-facing features are delivered in this milestone.

### Deliverables

- [x] README with product overview, local dev setup, and Plesk deployment notes
- [x] Architecture document (`docs/architecture.md`) — frontend, backend, storage, sync overview
- [x] Environment/config strategy — `.env.example` documented; `.env` excluded from git
- [x] PWA-first plan documented in `docs/product-spec.md` and `docs/architecture.md`
- [x] Security baseline checklist (`docs/security-checklist.md`)
- [x] Deployment notes targeting notes.defecttracker.uk (`docs/deployment-notes.md`)
- [x] Backup strategy notes for database and media (`docs/deployment-notes.md` §13)
- [x] Logging/diagnostics notes for Plesk/shared-hosting (`docs/deployment-notes.md` §14)
- [x] Milestone plan (`docs/milestones.md`)
- [x] Data model document (`docs/data-model.md`)
- [x] Sync strategy document (`docs/sync-strategy.md`)
- [x] QA checklist structure (`docs/qa-checklists/README.md`)

### Assumptions

- Plesk Obsidian or newer is available on the target server.
- Python 3.8+ is available on the Plesk server (no custom Python compilation required).
- SSH access to the server is available for initial setup.
- No Docker or container runtime is present or required.
- The domain `notes.defecttracker.uk` can be configured as a Plesk subdomain with Let's Encrypt SSL.
- A single-user model is sufficient for v1; multi-user auth is deferred to Milestone 5+.
- Local development requires only Python 3.8+ and a terminal (no Docker, no Node.js build step).

### File/Folder Structure Summary

```
notes/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── database.py          # SQLite helpers (get_db, init_db, close_db)
│   ├── routes.py            # API + page routes (placeholder; full implementation in M1)
│   ├── static/
│   │   ├── css/style.css
│   │   ├── js/app.js
│   │   ├── icons/           # PWA icons
│   │   ├── manifest.json
│   │   └── sw.js            # Service worker
│   └── templates/
│       └── index.html
├── docs/                    # All project documentation
│   ├── architecture.md      # ← this milestone (system architecture)
│   ├── product-spec.md
│   ├── milestones.md        # ← this file
│   ├── ui-screens.md
│   ├── data-model.md
│   ├── sync-strategy.md
│   ├── security-checklist.md
│   ├── deployment-notes.md  # Plesk deployment + backup + logging
│   └── qa-checklists/
│       └── README.md
├── migrations/              # SQL migration files (NNN_description.sql; none yet in M0)
│   └── README.md            # Migration instructions and naming convention
├── schema.sql               # DB schema (applied on first run)
├── wsgi.py                  # WSGI entry (local / gunicorn)
├── passenger_wsgi.py        # Plesk Passenger entry point
├── requirements.txt         # Pinned Python dependencies
├── run.sh                   # Local dev runner (no Docker)
├── .env.example             # Environment variable template (no secrets)
├── .gitignore               # Excludes .env, *.db, venv/, uploads/, *.log
├── CHANGELOG.md
└── DEPLOYMENT.md            # Legacy — superseded by docs/deployment-notes.md
```

### Acceptance Checklist — Milestone 0

- [x] `docs/architecture.md` exists and covers frontend, backend, storage, and sync strategy.
- [x] `README.md` documents product overview, local quick-start, and project structure.
- [x] Local dev works without Docker: `bash run.sh` starts the app at http://localhost:5000.
- [x] `.env.example` provides a template for all required environment variables.
- [x] `.env` is excluded from git (in `.gitignore`); no secrets committed to the repository.
- [x] `docs/deployment-notes.md` covers full Plesk deployment for notes.defecttracker.uk.
- [x] Backup strategy for `notes.db` (and future media) is documented.
- [x] Logging/diagnostics approach for Plesk/Passenger is documented.
- [x] `docs/security-checklist.md` provides a baseline security review checklist.
- [x] No Dockerfile, docker-compose.yml, or container-only scripts exist in the repository.
- [x] No auth or notes features are implemented beyond minimal scaffolding placeholders.

---

## Milestone 1 — Foundation (complete)

**Goal:** Deployable single-user notes app with PWA basics.

### Deliverables
- [x] Two-pane layout (list + editor)
- [x] Create / read / update / delete notes via REST API
- [x] SQLite backend with `user_id` column
- [x] Autosave (1.5 s debounce)
- [x] PWA manifest + service worker (app-shell cache)
- [x] Offline indicator banner
- [x] Plesk / Passenger WSGI deployment (`passenger_wsgi.py`)
- [x] Environment variable configuration (`.env`)
- [x] Project documentation (this file and siblings)

### Acceptance Criteria
- [ ] App loads at https://notes.defecttracker.uk within 3 s on a 4G connection.
- [ ] App shell loads from service-worker cache when offline (no network request to server).
- [ ] Creating and editing a note autosaves without a manual save action.
- [ ] Deleting a note requires a confirmation step.
- [ ] Offline indicator banner is visible when device has no network.
- [ ] App can be installed via browser "Add to home screen" on Chrome Android and Safari iOS.
- [ ] No Docker or container runtime is required to deploy or run the app.

---

## Milestone 2 — Sync Status & Offline Write Queue

**Goal:** Users always know whether their changes are saved; changes written offline sync on reconnect.

### Deliverables
- [ ] Sync status chip in the editor header: `Saved ✓` / `Saving…` / `Unsaved changes` / `Error ✗`
- [ ] IndexedDB offline write queue
- [ ] Automatic flush of queue on `online` event
- [ ] Retry with exponential back-off on sync error
- [ ] Visual indicator for queued (unsynced) notes in the list
- [ ] API endpoint for bulk sync (`POST /api/sync`)

### Acceptance Criteria
- [ ] Editing a note while offline shows "Unsaved changes" status.
- [ ] On reconnect, queued changes sync automatically without user action.
- [ ] If sync fails, "Error ✗" is shown with a manual retry button.
- [ ] After a successful save, status changes to "Saved ✓" within 200 ms.
- [ ] No data loss occurs when the browser is closed while changes are queued.
- [ ] The note list shows a visual badge on notes with unsynced local changes.

---

## Milestone 3 — Rich Content (Image Annotation & PDF Export)

**Goal:** Notes can contain images with canvas-drawn annotations; any note can be exported to PDF.

### Deliverables
- [ ] Markdown / rich-text editing toolbar (bold, italic, heading, list, code)
- [ ] Image attachment via drag-and-drop or file picker
- [ ] Image annotation: canvas overlay for freehand drawing
- [ ] Annotation persistence (SVG or merged PNG — decision OD-5 required)
- [ ] PDF export of current note (client-side or server-side — decision OD-4 required)
- [ ] API endpoints for media upload/download (`/api/notes/<id>/media`)

### Acceptance Criteria
- [ ] User can drag an image into the editor and see it inline.
- [ ] User can draw on an attached image and the annotation is saved with the note.
- [ ] Annotated images display correctly after a page reload.
- [ ] Clicking "Export PDF" produces a downloadable PDF that includes text and images.
- [ ] PDF renders correctly on Chrome, Firefox, and Safari.
- [ ] Rich-text content (bold, italic, lists) is preserved on round-trip (save → reload).

---

## Milestone 4 — Organisation (Search, Tags, Pinning)

**Goal:** Users can find and organise notes efficiently.

### Deliverables
- [ ] Full-text search (client-side filter; server-side SQLite FTS fallback)
- [ ] Tags / labels (free-form; stored in `note_tags` table)
- [ ] Tag colour coding
- [ ] Note pinning (up to 3 pinned notes at top of list)
- [ ] Sort options: by updated, created, title

### Acceptance Criteria
- [ ] Typing in the search box filters the note list in real time (< 100 ms).
- [ ] Tags can be created, applied to multiple notes, and deleted.
- [ ] Pinned notes always appear at the top of the list, regardless of sort order.
- [ ] Changing sort order persists across page reloads (localStorage).

---

## Milestone 5+ — Multi-User & Auth (Future)

**Goal:** Multiple users can have separate, isolated note collections.

> **Prerequisite:** Open decision OD-6 must be confirmed.

### Deliverables
- [ ] User registration (email + password)
- [ ] Login / logout
- [ ] Session management (server-side; CSRF protection)
- [ ] Per-user data isolation (existing `user_id` FK leveraged)
- [ ] Password reset flow (email link)
- [ ] Admin user management page (Plesk SSH or web UI)

### Acceptance Criteria
- [ ] Two different users cannot see each other's notes.
- [ ] Password is stored as a bcrypt hash (never plaintext).
- [ ] CSRF tokens are validated on all state-changing requests.
- [ ] Session expires after 30 days of inactivity.
- [ ] Password reset link expires after 1 hour.

---

## Milestone Summary Table

| Milestone | Theme | Status |
|---|---|---|
| M0 | Project Foundation & Architecture | ✅ Complete |
| M1 | Foundation | ✅ Complete |
| M2 | Sync Status & Offline Queue | 🔲 Planned |
| M3 | Rich Content (Annotations, PDF) | 🔲 Planned |
| M4 | Organisation (Search, Tags) | 🔲 Planned |
| M5+ | Multi-User & Auth | 🔲 Future |
