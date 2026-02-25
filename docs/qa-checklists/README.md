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
