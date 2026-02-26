# Milestone 6: Offline / Sync Design Notes

## Offline & Sync Design Summary

### Architecture

The offline/sync system is entirely client-side, using `localStorage` for persistence.  No additional server-side changes are required.

Three stores in `localStorage`:
| Key | Contents |
|-----|----------|
| `notes_sync_queue` | Array of pending save operations |
| `notes_offline_cache` | Last-known notes + folders list for offline display |
| `notes_sync_status` | Per-note sync status (synced / local / syncing / failed) |

### Sync Flow

1. **Online, edit succeeds**: PUT succeeds → status = `synced`.
2. **Online, PUT fails**: Entry added to sync queue → status = `failed`; retried on next reconnect.
3. **Offline, edit made**: Entry added to sync queue immediately (no network attempt) → status = `local`.
4. **Reconnects**: `window.online` fires → `processSyncQueue()` runs, retries all pending entries.
5. **Max retries (5) exceeded**: Entry removed from queue; status stays `failed`; error logged to console.

### Offline Note Viewing

When `loadNotes()` fails while offline, the app renders the most recently cached list from `notes_offline_cache`.  This cache is written after every successful load of the default (unfiltered, active) note list.

### Sync Status UI

Each note item in the list shows a small coloured badge when not in `synced` state:

| Status | Badge | Colour |
|--------|-------|--------|
| `local` | ● | Amber |
| `syncing` | ↻ | Blue |
| `failed` | ⚠ | Red |

The editor's autosave indicator shows `"Saved locally"` for offline/queued saves.

---

## Conflict Handling (v1 — Conflict Copy Strategy)

### Trigger
A conflict is detected when the server note's `updated_at` differs from the value we cached when we last fetched it (`cachedServerTs`).  This means another session (a different browser or device) has saved changes to the same note while we were offline.

### Resolution
1. **Create a conflict copy**: A new note is created via `POST /api/notes` with:
   - Title: `Conflict copy: <original title>`
   - Body: the server's current content
   - Same folder as the original
2. **Apply local changes**: The original note is overwritten with our local edits via `PUT /api/notes/<id>`.
3. **Result**: Both versions survive — the server copy is preserved as the conflict copy; our local edits win on the original.

### Limitations (v1)
- Conflict copies are not automatically cleaned up.
- No three-way merge (plain text editing makes this impractical without additional libraries).
- If the conflict-copy POST fails (e.g., network drops again mid-sync), the original is still synced; the conflict copy is lost silently (logged to console).

### Future Work
- Show a visible in-app notification when a conflict copy is created.
- Allow the user to review and merge conflict copies.
- Implement server-side `If-Unmodified-Since` / optimistic locking.

---

## Manual Offline Test Plan

### Setup
1. Open the app in Chrome DevTools (F12 → Network tab).
2. Log in and create at least three notes.
3. Confirm notes load and are visible.

### Test 1 — Offline viewing
1. In DevTools Network, set **Offline** throttling preset.
2. Reload the page.
3. **Expected**: Dashboard loads from service-worker cache; note list shows last-cached notes.
4. Click any note to open it.
5. **Expected**: Note title and body are visible (from cache).

### Test 2 — Offline editing & sync badge
1. While offline, edit the title or body of a note.
2. Wait for autosave (1.5 s) or navigate away and back.
3. **Expected**: The note in the list shows an amber ● badge.  Autosave indicator shows "Saved locally".
4. Re-enable network in DevTools.
5. **Expected**: Badge changes to blue ↻ (syncing), then disappears (synced).
6. Reload the page and confirm the edit is persisted on the server.

### Test 3 — Retry on reconnect
1. Go offline.
2. Edit two separate notes.
3. Go back online.
4. **Expected**: Both notes sync successfully; badges clear.
5. In another browser, verify both edits are visible.

### Test 4 — Conflict copy
1. Open the app in **two different browsers** (e.g., Chrome and Firefox).
2. In Browser A, go offline.
3. In Browser B, edit note "Alpha" and save.
4. In Browser A (still offline), edit note "Alpha" with different content.
5. Bring Browser A back online.
6. **Expected**: A new note "Conflict copy: Alpha" appears containing Browser B's version; the original "Alpha" contains Browser A's offline edit.

### Test 5 — Failed sync (max retries)
1. Open DevTools → Application → Service Workers → check "Offline".
2. Edit a note.
3. In the browser console, inspect `SyncQueue.getDiagnostics()`.
4. **Expected**: `queueLength: 1`, `syncStatuses` shows `failed` or `local`.
5. Check that `SyncQueue.logDiagnostics()` prints a table without exposing note content.

---

## PWA Install Test Steps

### Android Tablet (Chrome)
1. Open the app URL in Chrome on the tablet.
2. Tap the **⋮ menu** → "Add to Home screen" (or look for the install banner).
3. **Expected**: Install prompt appears with app name "Notes" and icon.
4. Confirm install.
5. **Expected**: App icon appears on the home screen.
6. Open from home screen.
7. **Expected**: App opens in standalone mode (no browser chrome/address bar).
8. Turn on Airplane Mode.
9. Open the app from the home screen.
10. **Expected**: App loads; last-cached notes are visible.

### Desktop Chrome
1. Open the app URL in Chrome.
2. Look for the **install icon** (⊕) in the address bar.
3. Click it → "Install Notes".
4. **Expected**: App opens in its own window without browser UI.
5. Pin the app to the taskbar.
6. Disconnect network; open the app.
7. **Expected**: App loads from cache; note list visible.

### Desktop Firefox
Firefox does not support PWA install natively; the offline caching (service worker) still works, but no install prompt will appear. Users can bookmark the app as a workaround.

### iOS Safari (iPhone/iPad)
1. Open the app URL in Safari.
2. Tap the **Share** button → "Add to Home Screen".
3. **Expected**: App is added; `apple-touch-icon` used for icon.
4. Open from home screen.
5. **Expected**: App opens in fullscreen (no Safari chrome).

---

## Debug / Diagnostic Notes (Self-Hosted Plesk)

### Service Worker registration failures
- The service worker at `/static/sw.js` must be served over HTTPS.  On Plesk, ensure the SSL certificate is valid and redirects from HTTP → HTTPS are configured.
- Check the browser console for `ServiceWorker registration failed` errors.
- In Chrome DevTools → Application → Service Workers, confirm the SW is registered and active.

### Diagnosing a stuck sync queue
Open the browser console on the app page and run:
```js
SyncQueue.logDiagnostics()
```
This prints a diagnostic table including queue length, queued note IDs, and cache age — without exposing note content.

To inspect the raw queue entries (note IDs only, no content):
```js
JSON.parse(localStorage.getItem('notes_sync_queue') || '[]')
  .map(e => ({ noteId: e.noteId, retries: e.retries, enqueuedAt: e.enqueuedAt }))
```

To manually clear a stuck queue (destructive — queued edits will be lost):
```js
localStorage.removeItem('notes_sync_queue')
```

### Cache invalidation after a server update
The service worker cache version is set to `notes-v2`.  After deploying an update that changes static files, bump the `CACHE_NAME` constant in `sw.js` (`app/static/sw.js`) to `notes-v3` (or higher).  This causes the old cache to be deleted on next activation.

### Plesk Passenger / WSGI headers
To ensure static files are served with correct MIME types (required for SW registration), confirm Plesk's nginx configuration for `/static/` is not stripping the `Content-Type` header.  The `sw.js` file must be served as `text/javascript` or `application/javascript`.

### LocalStorage quota
LocalStorage is limited to ~5 MB per origin.  The offline cache stores note text only (not images), so quota issues are unlikely for typical use.  If the app stops caching, check the console for `localStorage write failed` warnings from `sync.js`.
