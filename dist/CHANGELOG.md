# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned (Milestone 10)
- Email PDF — send a note's PDF export directly by email
- Batch export — download multiple notes as a ZIP or combined PDF

---

## [0.9.0] — Milestone 9

### Added
- Version history for every note (up to 50 snapshots per note, auto-pruned)
- Conflict copy detection when saving with a stale `client_updated_at` timestamp
- Version history side panel (🕐 button, slide-in drawer, Restore buttons)
- Conflict copies tab (⚠) in sidebar; read-only conflict copy editor
- `DELETE /api/conflicts/<id>` endpoint to permanently remove conflict copies
- 26 new automated tests (`tests/test_milestone9.py`); 257 total

---

## [0.8.0] — Milestone 8

### Added
- HTTP security headers: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- Input length validation: note title ≤ 500 chars, body ≤ 100 000 chars
- 500 error handler (JSON for API routes, styled page for browser routes)
- 413 handler for oversized uploads
- Settings page (`/settings`): username display, change password, dark mode toggle
- Release checklist (`docs/release-checklist.md`)

---

## [0.7.0] — Milestone 7

### Added
- Server-side PDF export via ReportLab (`GET /api/notes/<id>/export.pdf`)
- Annotation compositing in PDF (Pillow renders strokes before PDF embedding)
- Up to 20 images embedded per PDF export

---

## [0.6.0] — Milestone 6

### Added
- Progressive Web App improvements: background sync, offline write queue flush
- Service worker served at `/sw.js` with `Service-Worker-Allowed: /` header

---

## [0.5.0] — Milestone 5

### Added
- Multi-user authentication: login, logout, session management
- Per-user data isolation
- `flask create-user` CLI command for initial user bootstrap
- Protected routes: all API and dashboard routes require login

---

## [0.4.0] — Milestone 4

### Added
- Image upload from file picker and camera capture
- Image annotation canvas (pen, highlighter, arrow, rectangle, circle, text tools)
- `PUT /api/notes/<id>/images/<img_id>` — save annotation data
- `DELETE /api/notes/<id>/images/<img_id>` — delete image

---

## [0.3.0] — Milestone 3

### Added
- Folder management (create, rename, delete)
- Tag management (create, apply, filter)
- Full-text search (LIKE-based, with `|` escape character)
- Note pinning and archiving
- Sort options: by updated, created, title

---

## [0.2.0] — Milestone 2

### Added
- Sync status chip: Saved ✓ / Saving… / Unsaved changes / Error ✗
- IndexedDB offline write queue
- Automatic flush of queue on `online` event
- `POST /api/sync` bulk sync endpoint

---

### Added
- Two-pane layout: note list (left) + editor (right)
- Autosave with 1.5 s debounce
- PWA manifest and service worker (offline app-shell caching)
- Offline indicator banner
- Touch-friendly UI (minimum 44 px tap targets)
- Delete confirmation dialog
- REST API: list, create, get, update, delete notes
- SQLite backend with `user_id` column (single-user default, multi-user ready)
- Plesk / Passenger WSGI deployment support (`passenger_wsgi.py`)
- Environment variable configuration via `.env`

### Deployment target
- notes.defecttracker.uk (Plesk, Passenger WSGI, no Docker)
