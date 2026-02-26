# Offline & PWA — Design, Test Plans, and Debug Notes

> Milestone 6 deliverables: PWA installability, offline app shell, offline note cache, sync queue, and sync status UI.

---

## 1. Offline / Sync Design Summary

### Architecture overview

```
Browser (app.js)
  │
  ├─ IndexedDB: notes-pwa
  │   ├─ pending_writes  { note_id, title, body, is_pinned, folder_id, queued_at }
  │   └─ cached_notes    { id, title, body, …, cached_at }
  │
  ├─ Service Worker (notes-v2 cache)
  │   └─ App shell: /dashboard, CSS, JS, manifest, icons
  │
  └─ Server (Flask API)
      ├─ PUT /api/notes/<id>   (single save)
      └─ POST /api/sync        (bulk flush from queue)
```

### Sync state machine

Each open note tracks one of four sync states:

| State | Trigger | UI label (editor) | List badge |
|---|---|---|---|
| `synced` | Successful PUT / sync | Saved ✓ | none |
| `saving` | PUT in-flight | Saving… | blue pulse |
| `local` | Offline save | Saved locally | amber dot |
| `failed` | PUT/sync error | Save failed — tap to retry | red dot |

State transitions:

```
[synced / idle]
    │ user types
    ▼
[unsaved (timer pending)]
    │ 1.5 s debounce fires
    │ online? ──No──→ queueWrite(IDB) → [local]
    ▼ Yes
[saving] ──success──→ dequeueWrite → [synced]
         ──failure──→ queueWrite(IDB) → [failed]
                          │
                   tap indicator / online event
                          ▼
                    flushQueue() → [saving] → …
```

### Flush trigger points

1. `window` `online` event (automatic reconnect flush).
2. App startup — if pending writes exist and device is online.
3. User taps the "Save failed — tap to retry" autosave indicator.

### Flush algorithm (exponential back-off)

```
pending ← IndexedDB.pending_writes (sorted by queued_at ASC)
for each write:
    PUT /api/notes/<id>
    success → delete from IDB, syncState = synced
    failure → leave in IDB, syncState = failed, stop
if any failed:
    delay = min(2s × 2^retryCount, 60s)
    schedule retry after delay
```

### Offline note viewing

When `loadNotes()` fails because the device is offline, the app reads from `cached_notes` (populated on the last successful `loadNotes` call for the active, un-filtered view) and renders those notes. This gives the user read access to recently viewed notes without a network connection.

---

## 2. Conflict Handling — v1

**Strategy: last-write-wins (LWW) on the server.**

- The server does not compare `updated_at` timestamps — it always applies the incoming write.
- The client sends the full current title and body; no diffs or patches.
- If the user edits the same note on two devices and the second device syncs later, the second device's content wins.

**Why this is safe for v1:**

- The app is single-user (one account, typically one device).
- Offline edits accumulate in `pending_writes` keyed by `note_id`; only the most recent write per note is queued (older writes are overwritten in IDB).
- No silent data loss: if a sync fails it is retried; the user sees a clear "failed" indicator.

**Conflict detection (future milestone):**

A future version will send a `client_updated_at` timestamp with the write. The server will reject the write with `409 Conflict` if its `updated_at` is newer, and the client will create a conflict copy (appending `(conflict copy — <date>)` to the title) before syncing the server version.

---

## 3. Manual Offline Test Plan

### Pre-conditions

- App is running at `https://notes.defecttracker.uk` (or `http://localhost:5000`).
- You are logged in.
- At least 2–3 notes exist and have been viewed (to populate the cache).

### Test cases

#### T1 — App shell loads offline

1. Open DevTools → Network → set to "Offline".
2. Reload the page.
3. **Expected:** The app UI loads (from service worker cache). An amber banner "You're offline" is visible.

#### T2 — Note list visible offline

1. With DevTools still set to "Offline", look at the note list.
2. **Expected:** Previously viewed notes are shown (from IndexedDB cache). Note: search/filter may be limited to cached data.

#### T3 — Edit note while offline

1. Open a note.
2. Edit the title or body.
3. Wait 1.5 s (autosave debounce fires).
4. **Expected:** Autosave indicator shows "Saved locally". An amber dot appears next to the note in the list.

#### T4 — Reconnect triggers automatic sync

1. After T3, set DevTools → Network → "No throttling" (back online).
2. **Expected:** Within a few seconds, the amber dot changes to nothing (synced). The autosave indicator shows "Saved ✓".

#### T5 — Multiple offline edits sync correctly

1. Go offline.
2. Edit 3 different notes.
3. Go back online.
4. **Expected:** All 3 notes sync. Server reflects the edited content.

#### T6 — Edit fails — manual retry

1. Edit a note while online but simulate a server error (temporarily stop the server, or throttle to "Offline" after the save starts).
2. **Expected:** Autosave indicator shows "Save failed — tap to retry" (red text, underlined).
3. Tap the indicator.
4. **Expected:** Retry is attempted; on success shows "Saved ✓".

#### T7 — No data loss on browser close while offline

1. Go offline, edit a note (autosave fires → "Saved locally").
2. Close the browser tab.
3. Reopen the app.
4. Go online.
5. **Expected:** The offline edit is synced automatically on startup.

#### T8 — Offline banner hides when reconnected

1. Go offline → banner appears.
2. Go online.
3. **Expected:** Banner disappears immediately.

---

## 4. PWA Install Test Steps

### Android tablet (Chrome)

1. Open `https://notes.defecttracker.uk` in Chrome for Android.
2. Tap the browser menu (⋮).
3. Look for **"Add to Home screen"** or **"Install app"**.
4. **Expected:** An install prompt appears showing the "Notes" name and icon.
5. Confirm installation.
6. **Expected:** A "Notes" icon appears on the home screen / app drawer.
7. Tap the icon.
8. **Expected:** App opens in standalone mode (no browser address bar).
9. Verify the app header shows the correct theme colour (`#f5a623`).

**Chrome install criteria checklist:**
- [x] HTTPS served
- [x] `manifest.json` linked in `<head>`
- [x] `manifest.json` has `name`, `short_name`, `start_url`, `display: standalone`
- [x] 192×192 and 512×512 PNG icons
- [x] Service worker registered with scope `/`

### Desktop (Chrome / Edge)

1. Open `https://notes.defecttracker.uk` in Chrome or Edge on desktop.
2. Look for an **install icon** (⊕ or computer icon) in the address bar, or use the menu → "Install Notes…".
3. Click to install.
4. **Expected:** App opens as a standalone desktop window.
5. The window title should read "Notes".

### Safari on iOS / iPadOS

1. Open the app in Safari.
2. Tap the Share button → **"Add to Home Screen"**.
3. Confirm.
4. **Expected:** A "Notes" icon appears on the home screen.
5. **Note:** iOS Safari does not support service workers for full offline in the same way; the app shell will still load from browser cache in most cases.

---

## 5. Debug / Diagnostic Notes — Self-Hosted Plesk Setup

### Service worker scope

The service worker is served at `/sw.js` (via a Flask route) so it has scope `/` by default. If you see "Service-Worker-Allowed" header errors in the browser console, check:

```
GET /sw.js
Response headers should include:
  Service-Worker-Allowed: /
  Cache-Control: no-cache
```

If the SW is not registering, open DevTools → Application → Service Workers. Look for registration errors.

### Checking IndexedDB in DevTools

1. Open DevTools → Application → Storage → IndexedDB → `notes-pwa`.
2. `pending_writes` store shows notes that are queued for sync.
3. `cached_notes` store shows the offline note cache.
4. If `pending_writes` is non-empty and the app is online, a flush should happen automatically. If it doesn't, check the browser console for `[sync]` log messages.

### Console diagnostics

The sync queue logs to the browser console with `[sync]` and `[offline]` prefixes:

```
[sync] found 2 pending write(s) on startup
[sync] flushing 2 pending write(s)
[sync] flushed note 42
[sync] flush failed for note 43
[sync] retry in 4000 ms
[offline] serving 5 note(s) from cache
```

These logs are safe to leave enabled in production (no sensitive data is logged).

### Plesk / Passenger WSGI notes

- The `/sw.js` route is handled by Flask, not a static file server. Ensure Passenger is routing all requests to Flask (check `passenger_wsgi.py`).
- If `/sw.js` returns 404, check that the Flask blueprint is registered correctly and the route `/sw.js` is not blocked by `.htaccess` or Plesk's static file rules.
- HTTPS is required for service workers. Verify Let's Encrypt is active on the domain.

### Cache versioning

The service worker uses `CACHE_NAME = 'notes-v2'`. When deploying a new version with changed assets:

1. Increment the cache name (e.g. `notes-v3`).
2. The `activate` event deletes old caches automatically.
3. Users with the old service worker will get the new one on next visit.

If you need to force an immediate update during testing, use DevTools → Application → Service Workers → "Update" or "Unregister".

### Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| App doesn't load offline | SW not registered / scope wrong | Check `/sw.js` route and `Service-Worker-Allowed` header |
| Notes not showing offline | `cached_notes` IDB store empty | Load notes while online first; use the active (unfiltered) view |
| Sync badge stuck on amber | `pending_writes` not being flushed | Check console for `[sync]` errors; verify API is reachable |
| "Save failed" not retrying | `flushInProgress` flag stuck | Reload the page to reset state |
| PWA install prompt not showing | Manifest issue or not HTTPS | Verify manifest fields, icons, and HTTPS |
