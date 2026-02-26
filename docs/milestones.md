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
- [x] App loads at https://notes.defecttracker.uk within 3 s on a 4G connection.
- [x] App shell loads from service-worker cache when offline (no network request to server).
- [x] Creating and editing a note autosaves without a manual save action.
- [x] Deleting a note requires a confirmation step.
- [x] Offline indicator banner is visible when device has no network.
- [x] App can be installed via browser "Add to home screen" on Chrome Android and Safari iOS.
- [x] No Docker or container runtime is required to deploy or run the app.

---

## Milestone 2 — Sync Status & Offline Write Queue

**Goal:** Users always know whether their changes are saved; changes written offline sync on reconnect.

### Deliverables
- [x] Sync status chip in the editor header: `Saved ✓` / `Saving…` / `Unsaved changes` / `Error ✗`
- [x] IndexedDB offline write queue
- [x] Automatic flush of queue on `online` event
- [x] Retry with exponential back-off on sync error
- [x] Visual indicator for queued (unsynced) notes in the list
- [x] API endpoint for bulk sync (`POST /api/sync`)

### Acceptance Criteria
- [x] Editing a note while offline shows "Unsaved changes" status.
- [x] On reconnect, queued changes sync automatically without user action.
- [x] If sync fails, "Error ✗" is shown with a manual retry button.
- [x] After a successful save, status changes to "Saved ✓" within 200 ms.
- [x] No data loss occurs when the browser is closed while changes are queued.
- [x] The note list shows a visual badge on notes with unsynced local changes.

---

## Milestone 3 — Rich Content (Image Annotation & PDF Export)

**Goal:** Notes can contain images with canvas-drawn annotations; any note can be exported to PDF.

### Deliverables
- [x] Image attachment via drag-and-drop or file picker
- [x] Image annotation: canvas overlay for freehand drawing
- [x] Annotation persistence (stored as JSON in `note_images.annotation_data`)
- [x] PDF export of current note (server-side via ReportLab)
- [x] API endpoints for media upload/download (`/api/notes/<id>/images`)

### Acceptance Criteria
- [x] User can drag an image into the editor and see it inline.
- [x] User can draw on an attached image and the annotation is saved with the note.
- [x] Annotated images display correctly after a page reload.
- [x] Clicking "Export PDF" produces a downloadable PDF that includes text and images.
- [x] PDF renders correctly on Chrome, Firefox, and Safari.
- [x] Rich-text content (bold, italic, lists) is preserved on round-trip (save → reload).

---

## Milestone 4 — Organisation (Search, Tags, Pinning)

**Goal:** Users can find and organise notes efficiently.

### Deliverables
- [x] Full-text search (server-side SQLite LIKE query on title, body, tags)
- [x] Tags / labels (free-form; stored in `note_tags` table)
- [x] Note pinning (pinned notes at top of list)
- [x] Sort options: by updated, created, title
- [x] Folders (create/rename/delete; assign notes to a folder)

### Acceptance Criteria
- [x] Typing in the search box filters the note list in real time.
- [x] Tags can be created, applied to multiple notes, and deleted.
- [x] Pinned notes always appear at the top of the list, regardless of sort order.
- [x] Changing sort order persists across page reloads (localStorage).

---

## Milestone 5 — Multi-User & Auth (complete)

**Goal:** Multiple users can have separate, isolated note collections.

### Deliverables
- [x] Login / logout (username + password)
- [x] Session management (server-side; HttpOnly + SameSite=Lax cookies)
- [x] Per-user data isolation (all queries scoped to `user_id`)
- [x] CLI user creation (`flask create-user <username>`)
- [x] Settings page — change password, dark mode toggle

### Acceptance Criteria
- [x] Two different users cannot see each other's notes.
- [x] Password is stored as a bcrypt hash (never plaintext).
- [x] Session cookies are HttpOnly, SameSite=Lax.
- [x] Session expires after configurable days of inactivity (default 14 days).
- [x] No Docker or container runtime required.

---

---

## Milestone 8 — Hardening, QA, Polish & Operational Readiness (complete)

**Goal:** Production-ready hardening for personal use at notes.defecttracker.uk.

### Deliverables
- [x] HTTP security headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy)
- [x] Input length validation on note title (≤500 chars) and body (≤100 000 chars)
- [x] 500 error handler — JSON for API routes, styled error page for browser routes
- [x] 413 handler for oversized uploads
- [x] Settings page (`/settings`) — username display, change password form, dark mode toggle
- [x] Hardening summary (`docs/hardening-m8.md`)
- [x] Release checklist (`docs/release-checklist.md`)
- [x] Deployment runbook additions (`docs/deployment-notes.md` §16)
- [x] M8 QA checklist (`docs/qa-checklists/README.md`)

### Acceptance Criteria
- [x] All automated tests pass (231 tests).
- [x] Security headers verified present on all responses.
- [x] Input validation rejects payloads exceeding configured limits.
- [x] Settings page accessible only when authenticated.
- [x] Password change validated and persisted; old password invalidated.
- [x] Release checklist covers HTTPS, headers, auth, functional smoke test, backup, and monitoring.
- [x] No Docker or container runtime required.

---

## Milestone 9 — Version History & Conflict Copy Management (complete)

**Goal:** Protect user data by keeping a version history for every note and
surfacing merge-conflict copies when offline edits race with server updates.

### Deliverables

- [x] `note_versions` table — stores title + body snapshots (migration 005)
- [x] `conflict_of` column on `notes` — marks a note as a conflict copy
- [x] Snapshot on every save — current content snapshotted before overwriting
- [x] `GET /api/notes/<id>/versions` — list versions newest-first
- [x] `POST /api/notes/<id>/versions/<vid>/restore` — restore with pre-restore snapshot
- [x] `GET /api/conflicts` — list all conflict copies
- [x] `DELETE /api/conflicts/<id>` — permanently delete a conflict copy
- [x] Conflict detection in `PUT /api/notes/<id>` — stale `client_updated_at` triggers copy
- [x] Version History side panel (🕐 button, slide-in drawer, Restore buttons)
- [x] Conflict banner on conflict creation, **View Conflicts** shortcut
- [x] ⚠ Conflicts filter tab in sidebar; read-only conflict copy editor
- [x] **🗑️ Delete Conflict** toolbar button for conflict copies
- [x] 50-version cap per note with automatic pruning
- [x] Full test suite — 26 new tests in `tests/test_milestone9.py` (257 total)
- [x] `docs/versioning.md` — versioning model, conflict UX, retention notes, QA checklist
- [x] M9 QA checklist added to `docs/qa-checklists/README.md`

### Acceptance Criteria

- [x] Editing a note and saving creates a version snapshot automatically.
- [x] Restoring a previous version first saves the current content as a new snapshot.
- [x] Sending a stale `client_updated_at` creates a `[Conflict Copy]` note and returns `conflict_note_id`.
- [x] Conflict copies are visible in a dedicated ⚠ Conflicts tab and nowhere else.
- [x] Conflict copies are read-only; a **Delete Conflict** button removes them permanently.
- [x] A maximum of 50 versions per note are retained; older ones are pruned.
- [x] Version/conflict endpoints return 404 for unowned resources.
- [x] No Docker or container runtime required.

---

## Milestone Summary Table

| Milestone | Theme | Status |
|---|---|---|
| M0 | Project Foundation & Architecture | ✅ Complete |
| M1 | Foundation | ✅ Complete |
| M2 | Sync Status & Offline Queue | ✅ Complete |
| M3 | Rich Content (Annotations, PDF) | ✅ Complete |
| M4 | Organisation (Search, Tags) | ✅ Complete |
| M5 | Multi-User & Auth | ✅ Complete |
| M6 | PWA & Offline Improvements | ✅ Complete |
| M7 | PDF Export | ✅ Complete |
| M8 | Hardening, QA, Polish & Operational Readiness | ✅ Complete |
| M9 | Version History & Conflict Copy Management | ✅ Complete |
| M10 | Direct Email PDF + Batch Export | ✅ Complete |

---

## Milestone 10 — Direct Email PDF + Batch Export (complete)

**Goal:** Allow users to email a note's PDF directly from the app and to bulk-export multiple notes as a ZIP or combined PDF.

> Detailed planning is in [docs/milestone-10.md](milestone-10.md).

### Deliverables

- [x] `POST /api/notes/<id>/email-pdf` — send note PDF by email (SMTP, rate-limited)
- [x] `POST /api/batch-export` — export selected notes as ZIP or multi-note PDF
- [x] SMTP configuration via environment variables (host, port, user, pass, from)
- [x] Feature flag (`ENABLE_EMAIL_EXPORT`) — disabled by default
- [x] `email` column added to `users` table (migration `006_add_user_email.sql`)
- [x] `email_send_log` table for per-user rate limiting (max 10/hour)
- [x] Settings page: email address field for storing/updating user address
- [x] UI: "Email PDF" toolbar button enabled when `ENABLE_EMAIL_EXPORT=true`
- [x] UI: "Batch Export" toolbar button enabled when `ENABLE_EMAIL_EXPORT=true`
- [x] Rate limiting on email endpoint (per-user, max 10/hour)
- [x] Input validation: note ownership, batch size cap (max 50 notes)
- [x] Full test coverage for email path (mocked SMTP) and batch export (29 tests)

### Acceptance Criteria

- [x] Authenticated user can email a PDF of any of their own notes to their registered address.
- [x] Batch export downloads a ZIP containing one PDF per selected note, or a combined PDF.
- [x] Email send is rate-limited; excess requests return 429.
- [x] Unauthenticated requests return 401; other-user's notes return 404.
- [x] SMTP credentials are never logged or committed to the repository.
- [x] Feature remains disabled (`ENABLE_EMAIL_EXPORT=false`) until explicitly activated.
- [x] No Docker or container runtime required.

### Feature Status (stubs in place)

| Component | Status |
|---|---|
| `POST /api/notes/<id>/email-pdf` | ✅ Implemented |
| `POST /api/batch-export` | ✅ Implemented |
| `ENABLE_EMAIL_EXPORT` env flag | ✅ Implemented |
| `email` column on `users` table | ✅ Implemented (migration 006) |
| `email_send_log` rate-limit table | ✅ Implemented |
| Settings page: email address field | ✅ Implemented |
| UI button "Email PDF" (active when flag=true) | ✅ Implemented |
| UI button "Batch Export" (active when flag=true) | ✅ Implemented |
| Full email sending implementation | ✅ Implemented |
| Full batch export implementation | ✅ Implemented |
