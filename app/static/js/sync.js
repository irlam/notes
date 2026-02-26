/* ===== Offline Sync Queue ===== *
 * Manages a persistent sync queue in localStorage so offline edits are never
 * silently dropped.  Provides per-note sync status for the UI.
 *
 * Sync statuses:
 *   synced  – note matches server (no pending changes)
 *   local   – unsaved offline edit queued
 *   syncing – queue entry is actively being sent
 *   failed  – last sync attempt failed; will retry on reconnect
 *
 * Conflict strategy (v1 – conflict copy):
 *   When a queued entry is sent and the server note has been modified by
 *   another session since we last fetched it, the server's current content is
 *   preserved as a new note titled "Conflict copy: <original title>" before
 *   our local changes are applied.  This prevents silent data loss.
 */

const LS_QUEUE_KEY   = 'notes_sync_queue';
const LS_CACHE_KEY   = 'notes_offline_cache';
const LS_STATUS_KEY  = 'notes_sync_status';
const MAX_RETRIES    = 5;

/* ---- internal helpers ---- */

function _readJson(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || 'null') || fallback; }
  catch { return fallback; }
}

function _writeJson(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {
    console.warn('[sync] localStorage write failed', e);
  }
}

function _log(...args) { console.log('[sync]', ...args); }

/* ---- sync queue ---- */

function _getQueue()       { return _readJson(LS_QUEUE_KEY, []); }
function _setQueue(q)      { _writeJson(LS_QUEUE_KEY, q); }

/**
 * Enqueue a save for noteId.  Replaces any existing entry for that note
 * so only the latest edit is kept.
 *
 * @param {number}  noteId         Server note id.
 * @param {object}  payload        Body for PUT /api/notes/<id>.
 * @param {string}  cachedServerTs The server updated_at we last saw (for conflict check).
 */
function enqueueSave(noteId, payload, cachedServerTs) {
  const queue = _getQueue().filter(e => e.noteId !== noteId);
  queue.push({
    noteId,
    payload,
    cachedServerTs,
    retries: 0,
    enqueuedAt: new Date().toISOString()
  });
  _setQueue(queue);
  _setSyncStatus(noteId, 'local');
  _log('enqueued save for note', noteId);
  _dispatch();
}

/**
 * Process all queued saves.  Calls the provided apiRequest function.
 * createConflictCopy is called with the server note object when a conflict
 * is detected (should create a new note and return it, or null).
 *
 * @param {Function} apiRequest        (method, path, body?) => Promise<any>
 * @param {Function} createConflictCopy (serverNote) => Promise<void>
 */
async function processSyncQueue(apiRequest, createConflictCopy) {
  const queue = _getQueue();
  if (queue.length === 0) return;
  _log('processing', queue.length, 'queued saves');

  const remaining = [];

  for (const entry of queue) {
    _setSyncStatus(entry.noteId, 'syncing');
    _dispatch();
    try {
      // Conflict check: fetch current server state
      let serverNote = null;
      try {
        serverNote = await apiRequest('GET', `/api/notes/${entry.noteId}`);
      } catch (fetchErr) {
        // Note might have been deleted or is unreachable; re-queue
        throw fetchErr;
      }

      if (serverNote && entry.cachedServerTs && serverNote.updated_at !== entry.cachedServerTs) {
        _log('conflict detected for note', entry.noteId, '— creating conflict copy');
        if (createConflictCopy) {
          await createConflictCopy(serverNote);
        }
      }

      await apiRequest('PUT', `/api/notes/${entry.noteId}`, entry.payload);
      _setSyncStatus(entry.noteId, 'synced');
      _log('synced note', entry.noteId);
    } catch (e) {
      entry.retries = (entry.retries || 0) + 1;
      _log('sync failed for note', entry.noteId, 'attempt', entry.retries, e.message || e);
      if (entry.retries < MAX_RETRIES) {
        _setSyncStatus(entry.noteId, 'failed');
        remaining.push(entry);
      } else {
        _setSyncStatus(entry.noteId, 'failed');
        console.error('[sync] max retries reached for note', entry.noteId);
      }
    }
  }

  _setQueue(remaining);
  _dispatch();
}

/** Return how many items are pending in the queue. */
function queueLength() { return _getQueue().length; }

/* ---- per-note sync status ---- */

function _getStatuses()          { return _readJson(LS_STATUS_KEY, {}); }
function _setStatuses(s)         { _writeJson(LS_STATUS_KEY, s); }

function _setSyncStatus(noteId, status) {
  const s = _getStatuses();
  s[String(noteId)] = status;
  _setStatuses(s);
}

/** Return sync status string for a note id ('synced' if unknown). */
function getSyncStatus(noteId) {
  return _getStatuses()[String(noteId)] || 'synced';
}

/** Mark a note as synced (call after a successful online save). */
function markSynced(noteId) {
  _setSyncStatus(noteId, 'synced');
  // Remove from queue if present
  _setQueue(_getQueue().filter(e => e.noteId !== noteId));
}

/** Mark a note as syncing (call at start of a save attempt). */
function markSyncing(noteId) { _setSyncStatus(noteId, 'syncing'); }

/** Mark a note save as failed and optionally enqueue for retry. */
function markFailed(noteId, payload, cachedServerTs) {
  enqueueSave(noteId, payload, cachedServerTs);
  _setSyncStatus(noteId, 'failed');
  _dispatch();
}

/* ---- offline note cache ---- */

/**
 * Persist the full notes + folders arrays for offline viewing.
 * @param {Array} notesList
 * @param {Array} foldersList
 */
function cacheNotesData(notesList, foldersList) {
  _writeJson(LS_CACHE_KEY, {
    notes: notesList,
    folders: foldersList || [],
    savedAt: new Date().toISOString()
  });
}

/**
 * Return cached notes data, or null if nothing cached.
 * @returns {{ notes: Array, folders: Array, savedAt: string } | null}
 */
function getCachedNotesData() {
  return _readJson(LS_CACHE_KEY, null);
}

/**
 * Update a single note in the offline cache (after editing offline).
 * @param {object} noteObj
 */
function updateCachedNote(noteObj) {
  const cache = _readJson(LS_CACHE_KEY, null);
  if (!cache) return;
  const idx = cache.notes.findIndex(n => n.id === noteObj.id);
  if (idx !== -1) {
    cache.notes[idx] = { ...cache.notes[idx], ...noteObj };
  } else {
    cache.notes.unshift(noteObj);
  }
  _writeJson(LS_CACHE_KEY, cache);
}

/* ---- diagnostics ---- */

/**
 * Return a user-safe diagnostic object (no content, only metadata).
 * Useful for debugging sync issues in self-hosted setups.
 */
function getDiagnostics() {
  const queue = _getQueue();
  const statuses = _getStatuses();
  const cache = _readJson(LS_CACHE_KEY, null);
  return {
    queueLength: queue.length,
    queuedNoteIds: queue.map(e => e.noteId),
    syncStatuses: statuses,
    cachedNoteCount: cache ? cache.notes.length : 0,
    cacheAge: cache ? cache.savedAt : null,
    online: navigator.onLine,
    timestamp: new Date().toISOString()
  };
}

/** Log diagnostics to console (safe to call from browser devtools). */
function logDiagnostics() {
  console.group('[sync] Diagnostics');
  console.table(getDiagnostics());
  const queue = _getQueue();
  if (queue.length > 0) {
    console.log('Queue entries:', queue.map(e => ({
      noteId: e.noteId, retries: e.retries, enqueuedAt: e.enqueuedAt
    })));
  }
  console.groupEnd();
}

/* ---- custom event dispatcher ---- */

function _dispatch() {
  window.dispatchEvent(new CustomEvent('sync-status-changed'));
}

/* ---- public API ---- */
window.SyncQueue = {
  enqueueSave,
  processSyncQueue,
  queueLength,
  getSyncStatus,
  markSynced,
  markSyncing,
  markFailed,
  cacheNotesData,
  getCachedNotesData,
  updateCachedNote,
  getDiagnostics,
  logDiagnostics
};
