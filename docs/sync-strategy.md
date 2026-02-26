# Sync Strategy — Notes PWA

> Covers autosave behaviour, offline resilience, the write queue, and sync-status UI.
> Updated for Milestone 6 (PWA installability, offline basics, sync queue).

---

## 1. Autosave (online path)

The editor debounces every `input` event and fires a PUT request after **1.5 seconds of inactivity**.

```
User types → debounce timer resets → 1.5 s passes → PUT /api/notes/<id>
```

- If the user keeps typing, the timer resets continuously (no intermediate saves).
- A new note is created with POST on the first keystroke; subsequent saves use PUT.
- The status indicator in the editor header reflects the current sync state (see §2).

---

## 2. Sync Status States

The editor tracks a `syncState` variable reflected on the `autosave-indicator` element
via a `data-sync-state` attribute:

| State | `data-sync-state` | UI label | Colour |
|---|---|---|---|
| Saved | `synced` | Saved ✓ | Green |
| In-flight | `saving` | Saving… | Grey |
| Queued offline | `local` | ⚠ Queued offline | Amber |
| Error | `failed` | ✗ Failed — tap to retry | Red |

State transitions:

```
[idle/synced]
    │ user types
    ▼
[unsaved / timer running]
    │ debounce fires (1.5 s)
    │ device offline? ──Yes──→ [enqueue write to IndexedDB] → [local]
    ▼ No
[saving]  ──success──→ [synced]
          ──failure──→ [failed]  ──tap retry──→ [saving]
                                 ──device reconnects──→ [saving]
```

The "Failed" indicator is tappable — clicking it triggers `flushQueue()` immediately.

---

## 3. Offline Write Queue

### Storage

Pending writes are stored in **IndexedDB** (avoids the 5 MB localStorage quota and
synchronous I/O that can block the UI thread).

- Database: `notes-pwa` (version 1)
- Object store: `pending_writes`
- Key path: `note_id` (deduplicates — only the most recent pending write per note is kept)
- Value: `{ note_id, title, body, is_pinned, folder_id, queued_at }`

Using `note_id` as the key means if the user edits the same note multiple times offline,
only the latest state is stored and eventually synced — no redundant requests.

### Flush Triggers

The queue is flushed:
1. On the `window` `online` event (device reconnects).
2. On app startup when the queue is non-empty and the device is online.
3. Manually when the user taps the red "✗ Failed — tap to retry" status indicator.

### Flush Algorithm

```
for each entry in pending_writes (sorted by queued_at asc):
    PUT /api/notes/<note_id> { title, body, is_pinned, folder_id }
    on success:
        remove entry from IndexedDB
        clear pending badge from note list
        set syncState = 'synced' (if this note is open)
        reset backoff to 2 s
    on failure:
        set syncState = 'failed' (if this note is open)
        schedule retry after backoff delay
        double backoff (max 60 s)
        stop processing remaining entries
```

A `flushInProgress` mutex prevents concurrent flush runs (e.g. rapid `online` events).

### Conflict Resolution (v1 — Last-Write-Wins)

- The server always accepts the incoming PUT and updates `updated_at`.
- The offline queue stores the **last edit per note** only.
- If the same note was edited on another device while offline, the device that reconnects
  **last** wins. No merge is attempted.
- No data is silently dropped — the queue is drained and failures are visible to the user.
- Conflict detection (compare client `updated_at` vs server `updated_at` before applying)
  is planned for a future milestone.

---

## 4. Bulk Sync Endpoint — POST /api/sync

Allows the client to flush multiple queued writes in a single HTTP round-trip.

```
POST /api/sync
{
  "updates": [
    { "id": 42, "title": "...", "body": "...", "is_pinned": 0, "folder_id": null },
    ...
  ]
}

→ 200 OK
{
  "results": [
    { "id": 42, "ok": true },
    { "id": 99, "ok": false, "error": "not found" }
  ]
}
```

- Requires authentication (session cookie).
- Trashed notes and notes belonging to other users return `ok: false`.
- Invalid `id` types return `ok: false` (entry is skipped rather than aborting the batch).
- The current client implementation flushes one note at a time via individual PUT requests;
  POST /api/sync is available as a more efficient alternative for future optimisation.

---

## 5. Service Worker Caching

The service worker is registered at `/sw.js` (served by Flask with
`Service-Worker-Allowed: /`) so its scope covers the entire application.

### Cache strategy

| Request type | Strategy | Cache name |
|---|---|---|
| App shell (HTML, CSS, JS, icons, manifest) | Cache-first | `notes-v2` |
| `GET /api/notes*` | Network-first, cached fallback | `notes-list-v2` |
| Other `POST/PUT/DELETE /api/*` | Network-only (offline → 503) | — |

- Notes-list responses are cached on every successful network fetch.  
  When offline, the most recent cached response is served so the list is still readable.
- API writes are **not** served from cache. Offline writes go through the IndexedDB queue
  in `app.js`, not through the service worker.
- Old caches (`notes-v1`, `notes-list-v1`, etc.) are deleted on service-worker activation.

---

## 6. Data Integrity Guarantees

| Scenario | Behaviour |
|---|---|
| Browser closed with unsaved changes (online) | Autosave fires on `visibilitychange`; data likely saved |
| Browser closed with unsaved changes (offline) | IndexedDB queue persists; syncs on next online app open |
| Server error during save | `syncState = failed`; entry queued; user notified; tap to retry |
| Duplicate flush (rapid `online` events) | `flushInProgress` mutex prevents concurrent flushes |
| Same note edited on two devices (one offline) | Last reconnect wins (LWW); no silent data loss |
| New note created while offline | Creation fails gracefully (not queued in v1) |

---

## 7. Open Decisions (Sync)

| # | Question | Options | Decision |
|---|---|---|---|
| OD-1 | Offline queue storage | IndexedDB vs localStorage | **IndexedDB** ✅ implemented |
| OD-7 | Save on `beforeunload` | Synchronous XHR (deprecated) vs `navigator.sendBeacon` | **TBD** |
| OD-8 | Conflict resolution beyond LWW | Timestamp compare + user prompt | **TBD (future milestone)** |
| OD-9 | Offline note creation | Queue POST in IndexedDB with temp ID | **TBD (future milestone)** |

