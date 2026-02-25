# Milestones — Notes PWA

> **Deployment target:** notes.defecttracker.uk  
> **Hosting:** Plesk / Passenger WSGI — no Docker

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
| M1 | Foundation | ✅ Complete |
| M2 | Sync Status & Offline Queue | 🔲 Planned |
| M3 | Rich Content (Annotations, PDF) | 🔲 Planned |
| M4 | Organisation (Search, Tags) | 🔲 Planned |
| M5+ | Multi-User & Auth | 🔲 Future |
