# QA Checklists — Notes PWA

> Manual QA checklist structure for notes.defecttracker.uk.  
> These checklists are executed before each milestone release.

---

## How to Use

1. Copy the relevant checklist section into a new file named `QA-M<N>-YYYY-MM-DD.md`.
2. Work through each item on the target device/browser combination.
3. Mark each item ✅ Pass, ❌ Fail (with notes), or ⏭ Skip (with reason).
4. All items must be ✅ Pass or ⏭ Skip (with approved justification) before a milestone is signed off.

---

## Browser / Device Matrix

Run each checklist on at least the following combinations:

| # | Browser | Platform | Notes |
|---|---|---|---|
| B1 | Chrome (latest) | Windows 11 desktop | Primary test environment |
| B2 | Firefox (latest) | Windows 11 desktop | |
| B3 | Safari (latest) | macOS | |
| B4 | Chrome (latest) | Android (phone) | Touch + PWA install |
| B5 | Safari (latest) | iOS (iPhone) | Touch + PWA install |
| B6 | Edge (latest) | Windows 11 desktop | |

---

## Milestone 1 — Foundation QA

### M1-A: Loading & PWA

| # | Check | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|
| M1-A-01 | App loads at https://notes.defecttracker.uk within 3 s | | | | | |
| M1-A-02 | No console errors on initial load | | | | | |
| M1-A-03 | Service worker registered (DevTools → Application → SW) | | | | | |
| M1-A-04 | PWA manifest valid (DevTools → Application → Manifest) | | | | | |
| M1-A-05 | "Add to home screen" prompt appears (Chrome Android) | | | | n/a | |
| M1-A-06 | App installs and opens in standalone mode (no browser chrome) | | | | | |

### M1-B: Note CRUD

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M1-B-01 | Can create a new note via "+ New Note" button | | |
| M1-B-02 | Editing the title updates the note list item in real time | | |
| M1-B-03 | Autosave fires after ~1.5 s of inactivity (no manual save needed) | | |
| M1-B-04 | Reloading the page retains the last saved content | | |
| M1-B-05 | Deleting a note shows a confirmation dialog | | |
| M1-B-06 | Cancelling the delete dialog leaves the note intact | | |
| M1-B-07 | Confirming delete removes the note from the list | | |
| M1-B-08 | Selecting a different note loads its content in the editor | | |

### M1-C: Offline Behaviour

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M1-C-01 | Offline banner appears when network is disabled (DevTools → Network → Offline) | | |
| M1-C-02 | Offline banner disappears when network is restored | | |
| M1-C-03 | Previously loaded app shell (HTML/CSS/JS) is served from cache when offline | | |
| M1-C-04 | Note list loads from cache when offline (or graceful empty state shown) | | |

### M1-D: Responsive Layout

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M1-D-01 | Two-pane layout visible on desktop (≥ 768 px) | | |
| M1-D-02 | Single-pane (list or editor) shown on mobile (< 768 px) | | |
| M1-D-03 | All interactive elements are ≥ 44 × 44 px on mobile | | |
| M1-D-04 | No horizontal scrollbar on any viewport | | |

### M1-E: Accessibility

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M1-E-01 | All interactive elements are keyboard-focusable | | |
| M1-E-02 | Focus order is logical (left-to-right, top-to-bottom) | | |
| M1-E-03 | Delete confirmation dialog traps focus correctly | | |
| M1-E-04 | Colour contrast meets WCAG 2.1 AA (4.5:1 for normal text) | | |

### M1-F: Security Spot-Check

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M1-F-01 | HTTPS active; padlock shown in browser | | |
| M1-F-02 | HTTP redirects to HTTPS | | |
| M1-F-03 | `FLASK_ENV=production` confirmed (no debug toolbar visible) | | |
| M1-F-04 | `.env` is not accessible via the browser (`/env` returns 404) | | |

---

## Milestone 2 — Sync Status & Offline Queue QA

### M2-A: Sync Status Chip

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M2-A-01 | "Saved ✓" shown after a successful autosave | | |
| M2-A-02 | "Saving…" shown while a PUT request is in-flight | | |
| M2-A-03 | "Unsaved changes" shown immediately after typing | | |
| M2-A-04 | "Error ✗" shown when the server returns a non-2xx response | | |
| M2-A-05 | Tapping "Error ✗" triggers a manual retry | | |
| M2-A-06 | State transitions are animated (no jarring flicker) | | |

### M2-B: Offline Write Queue

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M2-B-01 | Editing a note while offline queues the write (IndexedDB visible in DevTools) | | |
| M2-B-02 | "Unsaved changes" badge shown on queued note in the list | | |
| M2-B-03 | Queue flushes automatically on reconnect | | |
| M2-B-04 | After flush, "Saved ✓" shown and badge removed | | |
| M2-B-05 | Closing and reopening the browser while offline retains the queue | | |
| M2-B-06 | No data loss when browser is closed with pending writes | | |

---

## Milestone 3 — Rich Content QA

### M3-A: Image Attachment

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M3-A-01 | Can drag and drop an image into the editor | | |
| M3-A-02 | Can use file picker to attach an image | | |
| M3-A-03 | Image is displayed inline in the note body | | |
| M3-A-04 | Image persists after page reload | | |
| M3-A-05 | Invalid file type (e.g. `.exe`) is rejected with an error message | | |
| M3-A-06 | File exceeding the size limit is rejected with an error message | | |

### M3-B: Image Annotation

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M3-B-01 | Clicking an image opens the annotation editor | | |
| M3-B-02 | Freehand drawing is visible on the canvas overlay | | |
| M3-B-03 | Saving the annotation persists it with the note | | |
| M3-B-04 | Annotation is displayed correctly on reload | | |
| M3-B-05 | Undo removes the last annotation stroke | | |
| M3-B-06 | Eraser tool removes drawn marks | | |

### M3-C: PDF Export

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M3-C-01 | "Export PDF" button is visible in the editor toolbar | | |
| M3-C-02 | Clicking Export PDF opens the print/save dialog | | |
| M3-C-03 | PDF includes the note title and body | | |
| M3-C-04 | PDF includes inline images | | |
| M3-C-05 | PDF renders correctly in Chrome, Firefox, and Safari | | |

---

## Milestone 4 — Organisation QA

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M4-01 | Typing in the search box filters notes in real time | | |
| M4-02 | Clearing the search box restores the full list | | |
| M4-03 | Can create a new tag and apply it to a note | | |
| M4-04 | Tags are shown as chips on notes in the list | | |
| M4-05 | Clicking a tag filters the list to notes with that tag | | |
| M4-06 | Can pin a note; pinned notes appear at the top of the list | | |
| M4-07 | Sort preference persists across page reloads | | |

---

## Milestone 8 — Hardening QA

### M8-A: Security Headers

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M8-A-01 | `X-Frame-Options: DENY` present on all responses | | |
| M8-A-02 | `X-Content-Type-Options: nosniff` present on all responses | | |
| M8-A-03 | `Referrer-Policy: strict-origin-when-cross-origin` present | | |
| M8-A-04 | `Permissions-Policy` restricts camera, microphone, geolocation | | |
| M8-A-05 | `Content-Security-Policy` contains `default-src 'self'` | | |
| M8-A-06 | No console CSP violations on dashboard page load | | |
| M8-A-07 | App cannot be embedded in an iframe (verify in DevTools) | | |

### M8-B: Input Validation

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M8-B-01 | Creating a note with a 501-character title returns 400 | | |
| M8-B-02 | Creating a note with body > 100,000 characters returns 400 | | |
| M8-B-03 | Updating a note with oversized title returns 400 | | |
| M8-B-04 | Normal notes (short title, reasonable body) still save correctly | | |

### M8-C: Settings Page

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M8-C-01 | `/settings` redirects to login when not authenticated | | |
| M8-C-02 | Settings page loads at `/settings` when logged in | | |
| M8-C-03 | Username is displayed on the settings page | | |
| M8-C-04 | Correct current password + valid new password → success message | | |
| M8-C-05 | Wrong current password → error message (no change) | | |
| M8-C-06 | New passwords don't match → error message | | |
| M8-C-07 | New password < 8 characters → error message | | |
| M8-C-08 | After password change, old password no longer works at login | | |
| M8-C-09 | Dark mode toggle persists across page reload (localStorage) | | |
| M8-C-10 | Settings link (⚙️) visible in sidebar footer | | |

### M8-D: Error Handling

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M8-D-01 | 404 for unknown API path returns JSON `{"error": "Not found"}` | | |
| M8-D-02 | Uploading a file > 12 MB returns 413 with JSON error body | | |

---

## Milestone 9 — Version History & Conflict Copy Management QA

> Full checklist is also included in `docs/versioning.md §4`.

### M9-A: Version History Panel

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-A-01 | 🕐 (history) button is visible in the toolbar when a note is open | | |
| M9-A-02 | Clicking 🕐 opens the Version History side panel | | |
| M9-A-03 | A brand-new note shows "No versions saved yet" in the panel | | |
| M9-A-04 | Editing and saving a note creates one version in the panel | | |
| M9-A-05 | Versions are listed newest-first with date/time label | | |
| M9-A-06 | Each version shows a truncated title preview | | |
| M9-A-07 | Pressing Escape or clicking the backdrop closes the panel | | |
| M9-A-08 | Clicking ✕ in the panel header closes it | | |
| M9-A-09 | History button is hidden for trashed notes | | |
| M9-A-10 | History button is hidden for conflict copies | | |

### M9-B: Restore a Version

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-B-01 | Clicking **Restore** on a version shows a confirmation prompt | | |
| M9-B-02 | Cancelling the prompt leaves the note unchanged | | |
| M9-B-03 | Confirming restore updates the editor with the old content | | |
| M9-B-04 | After restore, the version list grows by one (current content was snapshotted) | | |
| M9-B-05 | The note list is refreshed to show the restored title | | |
| M9-B-06 | Autosave indicator shows "Restored ✓" briefly | | |

### M9-C: Version Retention

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-C-01 | Saving a note 55 times results in ≤ 50 versions in the panel | | |
| M9-C-02 | Oldest versions are pruned (newest 50 retained) | | |

### M9-D: Conflict Copy Creation

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-D-01 | Saving without `client_updated_at` does **not** create a conflict copy | | |
| M9-D-02 | Saving with matching `client_updated_at` does **not** create a conflict copy | | |
| M9-D-03 | Saving with a stale `client_updated_at` creates a conflict copy and shows the banner | | |
| M9-D-04 | Conflict copy title starts with `[Conflict Copy]` | | |
| M9-D-05 | Conflict copy body contains the server's previous content | | |
| M9-D-06 | The ⚠️ conflict banner appears at the bottom of the screen | | |
| M9-D-07 | **View Conflicts** in the banner switches to the Conflicts tab | | |
| M9-D-08 | **✕** in the banner dismisses it | | |

### M9-E: Conflict Copy Management

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-E-01 | **⚠ Conflicts** tab is visible in the sidebar | | |
| M9-E-02 | The Conflicts tab lists all conflict copies (⚠ prefix on each) | | |
| M9-E-03 | Conflict copies do **not** appear in the Notes / Archived / Trash tabs | | |
| M9-E-04 | Opening a conflict copy shows the content in read-only mode | | |
| M9-E-05 | Title and body are not editable in a conflict copy | | |
| M9-E-06 | Pin / Archive / Folder / Tag controls are hidden for conflict copies | | |
| M9-E-07 | 🕐 history button is hidden for conflict copies | | |
| M9-E-08 | **🗑️ Delete Conflict** button is visible for a conflict copy | | |
| M9-E-09 | Clicking **Delete Conflict** removes the copy from the list | | |
| M9-E-10 | Attempting to delete a normal note via `DELETE /api/conflicts/<id>` returns 404 | | |
| M9-E-11 | Folder section is hidden in the Conflicts view | | |

### M9-F: Security & Access Control

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-F-01 | `GET /api/notes/<id>/versions` returns 401/302 when not logged in | | |
| M9-F-02 | `GET /api/notes/<id>/versions` returns 404 for another user's note | | |
| M9-F-03 | `POST /api/notes/<id>/versions/<vid>/restore` returns 404 for a version belonging to a different note | | |
| M9-F-04 | `GET /api/conflicts` returns 401/302 when not logged in | | |
| M9-F-05 | `DELETE /api/conflicts/<id>` returns 401/302 when not logged in | | |

---

## Regression Checklist (run on every release)

| # | Check |
|---|---|
| R-01 | Create a note, reload, confirm it persists |
| R-02 | Edit a note, wait for autosave, reload, confirm changes persist |
| R-03 | Delete a note, confirm it is removed |
| R-04 | App loads offline (service worker cache) |
| R-05 | Offline banner appears / disappears correctly |
| R-06 | No JavaScript console errors on any page |
| R-07 | HTTPS active and certificate valid |

---

## Milestone 10 — Email PDF + Batch Export Stubs

> These checks cover the M10 stub state (feature not yet implemented).
> Update this section when full M10 implementation is delivered.

### M10-A: Email PDF Stub

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M10-A-01 | ✉️ "Email PDF" button is visible but disabled in editor toolbar | | |
| M10-A-02 | Clicking the disabled button shows a "Coming soon" toast (not an error) | | |
| M10-A-03 | `POST /api/notes/<id>/email-pdf` (unauthenticated) returns 302 redirect | | |
| M10-A-04 | `POST /api/notes/<id>/email-pdf` (authenticated, flag off) returns 403 JSON | | |
| M10-A-05 | Response JSON contains `"feature": "email_pdf"` and `"milestone": 10` | | |

### M10-B: Batch Export Stub

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M10-B-01 | `POST /api/batch-export` (unauthenticated) returns 302 redirect | | |
| M10-B-02 | `POST /api/batch-export` (authenticated, flag off) returns 403 JSON | | |
| M10-B-03 | Response JSON contains `"feature": "batch_export"` and `"milestone": 10` | | |

### M10-C: Feature Flag

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M10-C-01 | `.env.example` contains `ENABLE_EMAIL_EXPORT=false` | | |
| M10-C-02 | With `ENABLE_EMAIL_EXPORT=true`, endpoints return 501 (not 403) | | |
| M10-C-03 | With `ENABLE_EMAIL_EXPORT=false` (default), endpoints return 403 | | |
