# Sync Strategy — Notes PWA

> Covers autosave behaviour, offline resilience, the write queue, and sync-status UI.

---

## 1. Autosave (current — M1)

The editor debounces every `input` event and fires a PUT request after **1.5 seconds of inactivity**.

```
User types → debounce timer resets → 1.5 s passes → PUT /api/notes/<id>
```

- If the user keeps typing, the timer resets continuously (no intermediate saves).
- A new note is created with POST on the first keystroke; subsequent saves use PUT.
- The autosave is **fire-and-forget** in v1 (no error handling beyond console logging).
- Sync-status UI (M2) will replace this with a proper state machine.

---

## 2. Sync Status States (Milestone 2)

The editor will track a `syncState` variable with four values:

| State | Trigger | UI label |
|---|---|---|
| `saved` | Successful PUT response | Saved ✓ |
| `saving` | PUT request in-flight | Saving… |
| `unsaved` | User typed; PUT not yet fired or queued offline | Unsaved changes |
| `error` | PUT returned non-2xx or network error | Error — tap to retry |

State transitions:

```
[idle/saved]
    │ user types
    ▼
[unsaved]
    │ debounce fires (1.5 s)
    │ device online?  ──No──→ [enqueue write to IndexedDB] → [unsaved]
    ▼ Yes
[saving]  ──success──→ [saved]
          ──failure──→ [error]  ──tap retry──→ [saving]
                                ──device reconnects──→ [saving]
```

---

## 3. Offline Write Queue (Milestone 2)

### Storage

Pending writes are stored in **IndexedDB** (not localStorage — avoids the 5 MB quota and blocking I/O).

Object store: `pending_writes`  
Key: `note_id`  
Value: `{ note_id, title, body, queued_at }`

Using `note_id` as the key means only the **most recent** pending write per note is retained, avoiding redundant network requests on flush.

### Flush Trigger

The queue is flushed:
1. On the `window` `online` event.
2. On app startup if the queue is non-empty and the device is online.
3. Manually when the user taps "Retry" on the Error chip.

### Flush Algorithm

```
for each entry in pending_writes (ordered by queued_at asc):
    PUT /api/notes/<note_id> { title, body }
    on success: remove entry from IndexedDB
    on failure: leave entry; mark syncState = error; stop flush
```

Retry uses **exponential back-off** starting at 2 s, capped at 60 s.

### Conflict Resolution (v1)

- **Last-write-wins** based on the server's `updated_at` timestamp.
- The server always accepts the incoming write and updates `updated_at`.
- No merge / three-way diff in v1.
- Conflict detection (based on `updated_at` comparison) is deferred to a future milestone.

---

## 4. Service Worker Caching (current — M1)

The service worker uses a **cache-first** strategy for the app shell (HTML, CSS, JS, manifest, icons) and a **network-first** strategy for API calls.

```
App shell request → Cache hit? → Serve from cache
                              → Cache miss → Fetch → Cache + serve

API request → Fetch → Success → serve response
                   → Network error + offline → return { error: 'offline' }
```

- Cache name is versioned (e.g. `notes-v1`); old caches are deleted on `activate`.
- API responses are **not** cached (notes data is managed by the offline write queue, not the service worker).

### Planned Improvement (M2)

- Cache the note list response for display while offline.
- Intercept PUT/POST/DELETE requests when offline and redirect to the IndexedDB queue.

---

## 5. Sync Indicator in Note List (Milestone 2)

Notes that have pending writes in IndexedDB will display a visual badge (e.g. a small amber dot) in the note list. This makes it clear at a glance which notes have not yet synced.

---

## 6. Data Integrity Guarantees

| Scenario | Behaviour |
|---|---|
| Browser closed with unsaved changes (online) | Autosave fires on `visibilitychange` / `beforeunload`; data likely saved |
| Browser closed with unsaved changes (offline) | IndexedDB queue persists; syncs on next app open with connectivity |
| Server error during save | `syncState = error`; entry remains in queue; user notified |
| Duplicate flush (e.g. rapid reconnect events) | Mutex flag prevents concurrent flushes |

---

## 7. Open Decisions (Sync)

| # | Question | Options | Decision |
|---|---|---|---|
| OD-1 | Offline queue storage | IndexedDB vs localStorage | **IndexedDB** (preferred; see §3) |
| OD-7 | Save on `beforeunload` | Synchronous XHR (deprecated) vs `navigator.sendBeacon` | **TBD** |
| OD-8 | Conflict resolution beyond LWW | Timestamp compare + user prompt | **TBD (future milestone)** |
