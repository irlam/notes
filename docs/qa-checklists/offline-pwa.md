# Offline & PWA — QA Checklists

> Covers manual offline testing, PWA install verification, and debug/diagnostic notes
> for the self-hosted Plesk setup at notes.defecttracker.uk.

---

## 1. Manual Offline Test Plan

### Pre-conditions
- App is loaded and logged in at least once (service worker + note list cached).
- Chrome DevTools or Firefox DevTools is available.

### Test A — Offline banner appears
1. Open the app in a browser.
2. In DevTools → Network tab, tick **Offline**.
3. **Expected:** Amber offline banner appears at the top of the app.
4. Untick Offline.
5. **Expected:** Banner disappears.

### Test B — App shell loads while offline
1. Load the app fully while online.
2. Set network to **Offline** in DevTools.
3. Hard-reload the page (`Ctrl+Shift+R` / `Cmd+Shift+R`).
4. **Expected:** App loads from cache — no blank screen, no 404 errors.
5. **Expected:** Note list shows cached notes (stale data from last online session).

### Test C — Edit note while offline; sync on reconnect
1. Open the app online. Open any note.
2. Set network to **Offline**.
3. Edit the note title or body.
4. Wait 1.5 s (autosave debounce).
5. **Expected:** Status indicator shows **"⚠ Queued offline"** (amber).
6. **Expected:** The note list shows an amber **●** badge next to the note.
7. Set network back to **Online**.
8. **Expected:** Status indicator transitions to **"Saving…"** then **"Saved ✓"**.
9. **Expected:** The amber badge disappears from the note list.
10. Reload the page and open the same note.
11. **Expected:** Changes are persisted on the server.

### Test D — No data loss on browser close while offline
1. Open the app online. Open a note.
2. Set network to **Offline**.
3. Edit the note and wait for "⚠ Queued offline" to appear.
4. Close the browser tab **without going back online**.
5. Reopen the app (still offline).
6. **Expected:** The pending badge is still visible — IndexedDB persisted the queued write.
7. Restore network.
8. **Expected:** The queued write flushes automatically and the badge clears.

### Test E — Sync failure retry
1. Open the app online. Open a note.
2. Simulate a server error (disconnect network or block via DevTools after the write is started).
3. Wait for autosave to fire.
4. **Expected:** Status indicator shows **"✗ Failed — tap to retry"** (red).
5. Restore connectivity.
6. Tap the red status indicator.
7. **Expected:** Retry fires, indicator transitions to "Saving…" then "Saved ✓".

### Test F — Offline note creation (not supported in v1)
1. Set network to **Offline**.
2. Click **+** to create a new note.
3. **Expected:** The creation attempt fails gracefully (no crash; the app remains usable).
4. **Note:** Creating new notes offline is a planned enhancement; existing note edits are queued.

---

## 2. PWA Install Test Steps

### 2a. Android tablet / phone (Chrome)
1. Navigate to `https://notes.defecttracker.uk` in Chrome for Android.
2. Tap the **⋮** menu (top-right).
3. **Expected:** "Add to Home screen" or "Install app" option appears.
4. Tap "Add to Home screen". Confirm the prompt.
5. **Expected:** App icon (orange "N") appears on the home screen.
6. Tap the icon.
7. **Expected:** App launches in standalone mode (no browser chrome / address bar).
8. **Expected:** Status bar matches the theme colour (`#f5a623`).

#### Troubleshooting — Chrome Android install prompt not shown
- Open `chrome://flags/#bypass-app-banner-engagement-checks` and enable it (dev only).
- Verify the manifest is served at `/static/manifest.json` and linked in the page `<head>`.
- Verify service worker is registered — open DevTools (remote debug) → Application → Service Workers.
- Verify HTTPS is active — PWA install requires a secure origin.

### 2b. Desktop (Chrome / Edge)
1. Navigate to `https://notes.defecttracker.uk` in Chrome or Edge.
2. Look for the **install icon** in the address bar (➕ or screen with arrow).
3. Click it and confirm.
4. **Expected:** App opens in its own window with no browser UI.
5. **Expected:** App appears in the OS application launcher / taskbar.

### 2c. Safari / iOS (Add to Home Screen)
1. Navigate to the app in Safari on iPhone or iPad.
2. Tap the **Share** button (square with upward arrow).
3. Tap **Add to Home Screen**.
4. **Expected:** App icon appears on the home screen.
5. **Expected:** App opens without Safari navigation bar (`apple-mobile-web-app-capable` meta tag).

---

## 3. Offline / Sync Design Summary

### Architecture
- **Service worker** (`/sw.js`, scope `/`): caches the app shell and notes-list API responses.
  Served with `Service-Worker-Allowed: /` and `Cache-Control: no-cache` headers from Flask.
- **IndexedDB write queue** (`notes-pwa` db, `pending_writes` store): persists note edits
  made while offline. Key = `note_id` (deduplicates per note; only most recent edit is kept).
- **Flush mechanism**: queue drains on the `window` `online` event, on app startup, and when
  the user manually taps the "Failed" status indicator.
- **Exponential backoff**: starts at 2 s, doubles each failed attempt, caps at 60 s.

### Sync States (editor header indicator)
| State | Trigger | Colour |
|---|---|---|
| *(empty)* | Default / no edits | — |
| Saving… | PUT request in-flight | Grey |
| Saved ✓ | PUT succeeded | Green |
| ⚠ Queued offline | Device offline, write queued | Amber |
| ✗ Failed — tap to retry | PUT failed (online) | Red |

### Note List Badge
- An amber **●** badge is shown next to note titles that have a pending write in IndexedDB.
- Badge clears when the write is flushed successfully.

---

## 4. Conflict Handling (v1)

**Strategy: last-write-wins (LWW)**

- The server `updated_at` timestamp is updated on every PUT.
- The offline queue stores the last edit per note. If the user edits the same note on two
  devices and one is offline, the device that reconnects last will overwrite the other.
- No merge or three-way diff is attempted in v1.
- **Safety guarantee:** offline writes are never silently dropped — they are queued and
  flushed. If the flush fails, the user sees the "Failed" indicator and can retry.
- Conflict detection (compare client `updated_at` vs server `updated_at`) is deferred to v2.

---

## 5. Debug / Diagnostic Notes for Plesk Self-Hosted Setup

### Verifying the service worker is registered
1. Open Chrome DevTools → **Application** → **Service Workers**.
2. Confirm a worker is registered for `https://notes.defecttracker.uk` with scope `/`.
3. If scope shows `/static/` instead of `/`, verify the `/sw.js` route is defined in
   `app/routes.py` and that `Service-Worker-Allowed: /` header is present.

### Checking cached assets
- DevTools → **Application** → **Cache Storage** → `notes-v2` lists app shell files.
- `notes-list-v2` contains the most recently cached `/api/notes` response.

### Checking the IndexedDB queue
- DevTools → **Application** → **IndexedDB** → `notes-pwa` → `pending_writes`.
- Each entry has `note_id`, `title`, `body`, `queued_at` (epoch ms).
- If entries remain after going online, check the browser console for `[Sync]` log lines.

### Common Plesk / Passenger WSGI issues
| Symptom | Likely cause | Fix |
|---|---|---|
| `/sw.js` returns 404 | Route not registered or Flask not reloaded | Restart Python app in Plesk; check `app/routes.py` |
| Service worker scope error in console | `/sw.js` missing `Service-Worker-Allowed: /` header | Ensure the `/sw.js` route adds the header |
| PWA install prompt never appears | HTTP only (no HTTPS) | Verify Let's Encrypt cert is active in Plesk |
| Old service worker still active | Cache not updated | DevTools → Application → Service Workers → "Update" |
| Sync always fails | CORS or session cookie issue | Check `SESSION_COOKIE_SAMESITE` and `SESSION_COOKIE_SECURE` |

### Log locations on Plesk
- Python/Passenger error log: `/var/log/passenger/notes.defecttracker.uk.log` (path varies by Plesk version)
- Nginx access log: Plesk → Domain → Logs
- Flask app logs: written to stderr (captured by Passenger)

### Enabling verbose sync logging
All sync operations log to `console.info`/`console.error` with the `[Sync]` prefix.
On a mobile device, use Chrome remote debugging (`chrome://inspect`) to view the console
while testing on Android.

To clear the IndexedDB queue manually during debugging:
```javascript
indexedDB.deleteDatabase('notes-pwa');
```
Then reload the page.
