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
5. **Authentication required** — login is required; all data is isolated per user; accounts are created via `flask create-user`.
6. **No Docker** — deployment is directly on the Plesk server via Passenger WSGI; container-only workflows are explicitly out of scope.

---

## 3. Feature Catalogue

### 3.1 Note Management (✅ implemented)

| ID | Feature | Notes |
|---|---|---|
| F-01 | Create note | Blank note, auto-titled by date if left empty |
| F-02 | View note list | Two-pane layout; sorted by `updated_at` descending |
| F-03 | Edit note | Title + body; autosave after 1.5 s of inactivity |
| F-04 | Delete note | Confirmation dialog; move to trash, then permanent delete |
| F-05 | Offline indicator | Banner shown when `navigator.onLine` is false |
| F-06 | PWA install | Manifest + service worker; add-to-home-screen prompt |
| F-07 | Archive / trash notes | Archive and trash tabs; restore or permanently delete |
| F-08 | Note pinning | Pinned notes always appear at the top of the list |

### 3.2 Sync Status (✅ implemented — Milestone 2)

| ID | Feature | Notes |
|---|---|---|
| F-10 | Sync status chip | Displays: Saved ✓ / Saving… / Unsaved changes / Error ✗ |
| F-11 | Offline write queue | IndexedDB queue; flushes on `online` event |
| F-12 | Conflict detection | `client_updated_at` timestamp-based; creates conflict copy |

### 3.3 Rich Content (✅ implemented — Milestones 3, 4, 7)

| ID | Feature | Notes |
|---|---|---|
| F-20 | Image attachment | File picker or camera capture; stored server-side in `uploads/` |
| F-21 | Image annotation | Canvas overlay; pen, highlighter, arrow, rectangle, circle, text tools |
| F-22 | PDF export | Server-side via ReportLab; `GET /api/notes/<id>/export.pdf` |

### 3.4 Organisation (✅ implemented — Milestone 3)

| ID | Feature | Notes |
|---|---|---|
| F-30 | Full-text search | LIKE-based search on title, body, and tag name |
| F-31 | Folders | Create/rename/delete folders; assign notes to a folder |
| F-32 | Tags / labels | Free-form tags; filter by tag |
| F-33 | Note pinning | Pin notes to top of list regardless of sort order |
| F-34 | Sort options | Recently edited, newest first, title A–Z |

### 3.5 Multi-User / Auth (✅ implemented — Milestone 5)

| ID | Feature | Notes |
|---|---|---|
| F-40 | Login / logout | Username + password; bcrypt hashed; session cookies |
| F-41 | Session management | Server-side sessions; HttpOnly + SameSite=Lax cookies |
| F-42 | Per-user data isolation | All queries scoped to `user_id = session['user_id']` |
| F-43 | CLI user creation | `flask create-user <username>` for initial bootstrap |
| F-44 | Settings page | Change password, dark mode toggle |

### 3.6 Version History (✅ implemented — Milestone 9)

| ID | Feature | Notes |
|---|---|---|
| F-50 | Version snapshots | Every save creates a `note_versions` record |
| F-51 | Version history panel | Slide-in drawer; restore any previous version |
| F-52 | Conflict copies | Stale `client_updated_at` creates a `[Conflict Copy]` note |
| F-53 | Conflict management | Dedicated ⚠ Conflicts tab; delete conflict copies permanently |

### 3.7 Email PDF + Batch Export (✅ implemented — Milestone 10)

| ID | Feature | Notes |
|---|---|---|
| F-60 | Email PDF | `POST /api/notes/<id>/email-pdf` — SMTP, rate-limited (10/hour); requires `ENABLE_EMAIL_EXPORT=true` |
| F-61 | Batch export | `POST /api/batch-export` — ZIP (one PDF/note) or combined PDF; max 50 notes; requires `ENABLE_EMAIL_EXPORT=true` |
| F-62 | User email address | Stored in `users.email`; editable on Settings page; used as the To: address for Email PDF |

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

## 5. Out of Scope (current)

- Real-time collaborative editing
- Native mobile apps (iOS/Android)
- Docker / container deployment
- Note sharing / public links

---

## 6. Open Decisions (resolved)

| # | Question | Decision |
|---|---|---|
| OD-1 | Offline write storage mechanism | IndexedDB |
| OD-2 | Rich-text format stored in DB | Plain text (contenteditable div) |
| OD-3 | Image storage location | Server filesystem (`uploads/`) |
| OD-4 | PDF export approach | Server-side ReportLab |
| OD-5 | Annotation persistence format | Canvas PNG merged server-side (Pillow) |
| OD-6 | Multi-user auth trigger milestone | After M4 or after M3? | **TBD** |
