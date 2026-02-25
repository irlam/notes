# Product Specification — Notes PWA

**App name:** Notes  
**Deployment target:** notes.defecttracker.uk  
**Hosting:** Plesk (Passenger WSGI, Python) — **no Docker / no containers**  
**Architecture:** PWA-first (installable, offline-capable)  
**Primary user model:** Single-user-first; data model multi-user-ready

---

## 1. Purpose

A fast, distraction-free personal note-taking web application that behaves like a native app when installed as a PWA. The app must remain fully functional when offline (for previously cached notes), syncing changes silently when connectivity is restored.

---

## 2. Core Principles

1. **PWA-first** — installable on desktop and mobile; offline mode is a first-class concern.
2. **Autosave** — no explicit "Save" button; changes are persisted automatically.
3. **Offline resilience** — notes can be read and edited without a network connection; writes are queued and synced on reconnect.
4. **Sync status transparency** — the UI always shows whether the last save succeeded, is pending, or failed.
5. **Single-user-first** — no login required in v1; the data model supports adding users later without a migration.
6. **No Docker** — deployment is directly on the Plesk server via Passenger WSGI; container-only workflows are explicitly out of scope.

---

## 3. Feature Catalogue

### 3.1 Note Management (v0.1 — implemented)

| ID | Feature | Notes |
|---|---|---|
| F-01 | Create note | Blank note, auto-titled by date if left empty |
| F-02 | View note list | Two-pane layout; sorted by `updated_at` descending |
| F-03 | Edit note | Title + body; autosave after 1.5 s of inactivity |
| F-04 | Delete note | Confirmation dialog; 204 response |
| F-05 | Offline indicator | Banner shown when `navigator.onLine` is false |
| F-06 | PWA install | Manifest + service worker; add-to-home-screen prompt |

### 3.2 Sync Status (planned — Milestone 2)

| ID | Feature | Notes |
|---|---|---|
| F-10 | Sync status chip | Displays: Saved ✓ / Saving… / Unsaved changes / Error ✗ |
| F-11 | Offline write queue | IndexedDB queue; flushes on `online` event |
| F-12 | Conflict resolution | Last-write-wins in v1; timestamp-based |

### 3.3 Rich Content (planned — Milestone 3)

| ID | Feature | Notes |
|---|---|---|
| F-20 | Markdown / rich-text editing | Toolbar with bold, italic, heading, list, code |
| F-21 | Image attachment | Drag-and-drop or file picker; stored server-side |
| F-22 | Image annotation | Canvas overlay drawing on attached images |
| F-23 | PDF export | Client-side render via `window.print()` or a PDF library |

### 3.4 Organisation (planned — Milestone 4)

| ID | Feature | Notes |
|---|---|---|
| F-30 | Full-text search | Client-side filter for speed; server-side FTS as fallback |
| F-31 | Tags / labels | Free-form tags; colour coding optional |
| F-32 | Note pinning | Pin up to 3 notes to top of list |

### 3.5 Multi-User / Auth (future — Milestone 5+)

| ID | Feature | Notes |
|---|---|---|
| F-40 | User registration & login | Email + password; bcrypt hashed |
| F-41 | Session management | Server-side sessions; CSRF protection |
| F-42 | Per-user data isolation | `user_id` FK already in schema |

---

## 4. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Time to interactive (cold, 3G) | < 3 s |
| Autosave latency | ≤ 1.5 s after last keystroke |
| Offline functionality | Read all cached notes; queue writes |
| Accessibility | WCAG 2.1 AA |
| Mobile touch targets | ≥ 44 × 44 px |
| Browser support | Chrome 90+, Firefox 90+, Safari 15+, Edge 90+ |

---

## 5. Out of Scope (v1)

- Real-time collaborative editing
- Native mobile apps (iOS/Android)
- Docker / container deployment
- Email notifications
- Note sharing / public links

---

## 6. Open Decisions

> These must be confirmed before Milestone 2 coding begins.

| # | Question | Options | Decision |
|---|---|---|---|
| OD-1 | Offline write storage mechanism | IndexedDB vs localStorage | **TBD** |
| OD-2 | Rich-text format stored in DB | HTML vs Markdown vs Delta (Quill) | **TBD** |
| OD-3 | Image storage location | Server filesystem vs SQLite BLOB vs object store | **TBD** |
| OD-4 | PDF export approach | `window.print()` CSS + `@media print` vs jsPDF vs Puppeteer server-side | **TBD** |
| OD-5 | Annotation persistence format | SVG overlay vs Canvas PNG merged into image | **TBD** |
| OD-6 | Multi-user auth trigger milestone | After M4 or after M3? | **TBD** |
