/* ===== Dark mode preference ===== */
// Apply before the rest of the page initialises to avoid a flash of light mode.
if (localStorage.getItem('notes_dark_mode') === '1') {
  document.documentElement.setAttribute('data-theme', 'dark');
}

/* ===== State ===== */
let notes = [];
let folders = [];
let tags = [];
let images = [];   // images for the currently open note
let currentNoteId = null;
let autosaveTimer = null;
let searchTimer = null;
let isSaving = false;
let currentFilter = 'active';
let currentFolderId = null;   // null = all, number = filter by folder
let currentSort = 'updated_desc';
let searchQuery = '';
let historyNoteId = null;    // note whose history panel is open

/* ===== Constants ===== */
const DAY_MS = 86400000;
const SEARCH_DEBOUNCE_MS = 300;
const SYNC_RETRY_BASE_MS = 2000;
const SYNC_RETRY_MAX_MS = 60000;

/* ===== Sync State ===== */
// Map of noteId (number) -> 'synced'|'saving'|'local'|'failed'
const syncStates = new Map();
let flushInProgress = false;
let flushRetryTimer = null;
let flushRetryCount = 0;

/* ===== IndexedDB helpers ===== */
let _idb = null;

function openIDB() {
  if (_idb) return Promise.resolve(_idb);
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('notes-pwa', 1);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('pending_writes')) {
        db.createObjectStore('pending_writes', { keyPath: 'note_id' });
      }
      if (!db.objectStoreNames.contains('cached_notes')) {
        db.createObjectStore('cached_notes', { keyPath: 'id' });
      }
    };
    req.onsuccess = e => { _idb = e.target.result; resolve(_idb); };
    req.onerror = () => reject(req.error);
  });
}

async function idbPut(storeName, value) {
  const db = await openIDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    tx.objectStore(storeName).put(value);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function idbGet(storeName, key) {
  const db = await openIDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const req = tx.objectStore(storeName).get(key);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbDelete(storeName, key) {
  const db = await openIDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    tx.objectStore(storeName).delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function idbGetAll(storeName) {
  const db = await openIDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const req = tx.objectStore(storeName).getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbClear(storeName) {
  const db = await openIDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    tx.objectStore(storeName).clear();
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

/* ===== Sync state helpers ===== */
function setSyncState(noteId, state) {
  syncStates.set(noteId, state);
  if (currentNoteId === noteId) {
    updateAutosaveFromSync(state);
  }
  updateNoteItemBadge(noteId, state);
}

function getSyncState(noteId) {
  return syncStates.get(noteId) || 'synced';
}

function updateAutosaveFromSync(state) {
  const msgs = {
    synced: 'Saved \u2713',
    saving: 'Saving\u2026',
    local: 'Saved locally',
    failed: 'Save failed \u2014 tap to retry',
  };
  setAutosave(msgs[state] || '');
  if (autosaveEl) {
    autosaveEl.dataset.syncState = state;
  }
}

function updateNoteItemBadge(noteId, state) {
  const el = noteList.querySelector(`.note-item[data-id="${noteId}"]`);
  if (!el) return;
  let badge = el.querySelector('.sync-badge');
  if (state === 'synced') {
    if (badge) badge.remove();
    return;
  }
  if (!badge) {
    badge = document.createElement('span');
    badge.className = 'sync-badge';
    badge.setAttribute('aria-label', 'Sync status');
    el.appendChild(badge);
  }
  badge.dataset.state = state;
  const titles = { local: 'Saved locally — pending sync', saving: 'Syncing…', failed: 'Sync failed' };
  badge.title = titles[state] || state;
}

/* ===== Pending writes queue ===== */
async function queueWrite(noteId, title, body, body_after, is_pinned, folder_id) {
  try {
    await idbPut('pending_writes', {
      note_id: noteId,
      title,
      body,
      body_after,
      is_pinned,
      folder_id: folder_id != null ? folder_id : null,
      queued_at: Date.now(),
    });
    console.log('[sync] queued write for note', noteId);
  } catch (e) {
    console.error('[sync] failed to queue write', e);
  }
}

async function dequeueWrite(noteId) {
  try {
    await idbDelete('pending_writes', noteId);
  } catch (e) {
    console.error('[sync] failed to dequeue write', e);
  }
}

async function getPendingWrites() {
  try {
    return await idbGetAll('pending_writes');
  } catch (e) {
    console.error('[sync] failed to read pending writes', e);
    return [];
  }
}

/* ===== Note cache (for offline viewing) ===== */
async function cacheNotes(notesList) {
  try {
    for (const n of notesList) {
      await idbPut('cached_notes', { ...n, cached_at: Date.now() });
    }
  } catch (e) {
    console.error('[sync] failed to cache notes', e);
  }
}

async function getCachedNotes() {
  try {
    return await idbGetAll('cached_notes');
  } catch (e) {
    console.error('[sync] failed to get cached notes', e);
    return [];
  }
}

/* ===== Flush queue ===== */
async function flushQueue() {
  if (flushInProgress || !navigator.onLine) return;
  const pending = await getPendingWrites();
  if (pending.length === 0) return;

  flushInProgress = true;
  clearTimeout(flushRetryTimer);
  console.log('[sync] flushing', pending.length, 'pending write(s)');

  // Sort by queued_at ascending
  pending.sort((a, b) => a.queued_at - b.queued_at);

  let anyFailed = false;
  for (const w of pending) {
    setSyncState(w.note_id, 'saving');
    try {
      const updated = await apiRequest('PUT', `/api/notes/${w.note_id}`, {
        title: w.title,
        body: w.body,
        body_after: w.body_after || '',
        is_pinned: w.is_pinned,
        folder_id: w.folder_id,
      });
      await dequeueWrite(w.note_id);
      const idx = notes.findIndex(n => n.id === w.note_id);
      if (idx !== -1) notes[idx] = updated;
      setSyncState(w.note_id, 'synced');
      await idbPut('cached_notes', { ...updated, cached_at: Date.now() });
      console.log('[sync] flushed note', w.note_id);
    } catch (e) {
      console.error('[sync] flush failed for note', w.note_id, e);
      setSyncState(w.note_id, 'failed');
      anyFailed = true;
    }
  }

  if (!anyFailed) {
    flushRetryCount = 0;
  } else {
    // Exponential back-off retry
    const delay = Math.min(SYNC_RETRY_BASE_MS * (2 ** flushRetryCount), SYNC_RETRY_MAX_MS);
    flushRetryCount++;
    console.log('[sync] retry in', delay, 'ms');
    flushRetryTimer = setTimeout(() => {
      flushInProgress = false;
      flushQueue();
    }, delay);
  }

  if (!anyFailed) {
    flushInProgress = false;
    renderList();
  }
}

/* ===== DOM refs ===== */
const noteList = document.getElementById('note-list');
const noteTitle = document.getElementById('note-title');
const noteBody = document.getElementById('note-body');
const noteBodyAfter = document.getElementById('note-body-after');
const autosaveEl = document.getElementById('autosave-indicator');
const offlineBanner = document.getElementById('offline-banner');
const btnNew = document.getElementById('btn-new');
const btnBack = document.getElementById('btn-back');
const btnPin = document.getElementById('btn-pin');
const btnArchive = document.getElementById('btn-archive');
const btnExportPdf = document.getElementById('btn-export-pdf');
const btnTrash = document.getElementById('btn-trash');
const btnRestore = document.getElementById('btn-restore');
const btnDeletePermanent = document.getElementById('btn-delete-permanent');
const btnDeleteConflict = document.getElementById('btn-delete-conflict');
const mainLayout = document.querySelector('.main-layout');
const editorContent = document.getElementById('editor-content');
const editorWelcome = document.getElementById('editor-welcome');
const dialogOverlay = document.getElementById('dialog-overlay');
const btnCancelDelete = document.getElementById('btn-cancel-delete');
const btnConfirmDelete = document.getElementById('btn-confirm-delete');
const filterTabs = document.querySelectorAll('.filter-tab');
const searchInput = document.getElementById('search-input');
const folderSection = document.getElementById('folder-section');
const folderListEl = document.getElementById('folder-list');
const btnNewFolder = document.getElementById('btn-new-folder');
const newFolderForm = document.getElementById('new-folder-form');
const newFolderInput = document.getElementById('new-folder-input');
const sortSelect = document.getElementById('sort-select');
const noteFolderSelect = document.getElementById('note-folder-select');
const tagBar = document.getElementById('tag-bar');
const tagChipsEl = document.getElementById('tag-chips');
const tagInput = document.getElementById('tag-input');
const tagDatalist = document.getElementById('tag-datalist');
const imageToolbar = document.getElementById('image-toolbar');
const btnUploadImage = document.getElementById('btn-upload-image');
const btnCameraCapture = document.getElementById('btn-camera-capture');
const inputUploadImage = document.getElementById('input-upload-image');
const inputCameraCapture = document.getElementById('input-camera-capture');
const imageUploadStatus = document.getElementById('image-upload-status');
const imageBlocksEl = document.getElementById('image-blocks');
const btnHistory = document.getElementById('btn-history');
const historyPanel = document.getElementById('history-panel');
const historyList = document.getElementById('history-list');
const btnCloseHistory = document.getElementById('btn-close-history');
const conflictBanner = document.getElementById('conflict-banner');
const btnViewConflicts = document.getElementById('btn-view-conflicts');
const btnDismissConflictBanner = document.getElementById('btn-dismiss-conflict-banner');

/* ===== Formatting toolbar refs ===== */
const fmtBar       = document.getElementById('fmt-bar');
const fmtBtnBold   = document.getElementById('fmt-bold');
const fmtBtnItalic = document.getElementById('fmt-italic');
const fmtBtnUnder  = document.getElementById('fmt-underline');
const fmtBtnStrike = document.getElementById('fmt-strike');
const fmtColor     = document.getElementById('fmt-color');
const fmtHighlight = document.getElementById('fmt-highlight');
const fmtSize      = document.getElementById('fmt-size');
const fmtBtnUl     = document.getElementById('fmt-ul');
const fmtBtnOl     = document.getElementById('fmt-ol');
const fmtBtnClear  = document.getElementById('fmt-clear');

/* ===== Helpers ===== */
function formatDate(dateStr) {
  const d = new Date(dateStr.replace(' ', 'T') + (dateStr.includes('T') ? '' : 'Z'));
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const itemDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const dayDiff = Math.round((today - itemDay) / DAY_MS);

  if (dayDiff === 0) {
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  } else if (dayDiff === 1) {
    return 'Yesterday';
  } else if (dayDiff < 7) {
    return d.toLocaleDateString('en-GB', { weekday: 'short' });
  } else {
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' });
  }
}

function stripHtml(html) {
  if (!html) return '';
  try {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    return (doc.body.textContent || '').replace(/\s+/g, ' ').trim();
  } catch (_) {
    return html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
  }
}

function getTitle(note) {
  return note.title.trim() || 'Untitled';
}

function getSubtitle(note) {
  const plain = stripHtml(note.body);
  const first = plain.split('\n')[0];
  return first.trim() || '—';
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function currentNote() {
  return notes.find(n => n.id === currentNoteId) || null;
}

/* ===== Rendering ===== */
function renderList() {
  if (notes.length === 0) {
    const msgs = {
      active: 'No notes yet.<br>Tap <strong>+</strong> to create one.',
      archived: 'No archived notes.',
      trashed: 'Trash is empty.',
    };
    const msg = searchQuery
      ? 'No notes match your search.'
      : (msgs[currentFilter] || msgs.active);
    noteList.innerHTML = `
      <div class="empty-state">
        <div class="icon">📝</div>
        <p>${msg}</p>
      </div>`;
    return;
  }
  noteList.innerHTML = notes.map(n => {
    const tagHtml = n.tags && n.tags.length
      ? `<div class="note-item-tags">${n.tags.slice(0, 3).map(t =>
          `<span class="note-tag-chip">${escapeHtml(t.name)}</span>`
        ).join('')}${n.tags.length > 3 ? `<span class="note-tag-more">+${n.tags.length - 3}</span>` : ''}</div>`
      : '';
    const state = getSyncState(n.id);
    const badgeHtml = (state !== 'synced')
      ? `<span class="sync-badge" data-state="${state}" title="${
          state === 'local' ? 'Saved locally \u2014 pending sync' :
          state === 'saving' ? 'Syncing\u2026' : 'Sync failed'
        }" aria-label="Sync status"></span>`
      : '';
    const isConflict = !!n.conflict_of;
    const dateLabel = isConflict ? 'Conflict Copy' : `Edited ${formatDate(n.updated_at)}`;
    return `
    <div class="note-item ${n.id === currentNoteId ? 'active' : ''}${isConflict ? ' conflict-item' : ''}" data-id="${n.id}" role="listitem">
      <div class="note-item-header">
        <div class="note-item-title">${escapeHtml(getTitle(n))}</div>
        ${n.is_pinned ? '<span class="note-pin-badge" aria-label="Pinned">📌</span>' : ''}
        ${badgeHtml}
      </div>
      <div class="note-item-subtitle">${escapeHtml(getSubtitle(n))}</div>
      ${tagHtml}
      <div class="note-item-date">${dateLabel}</div>
    </div>`;
  }).join('');

  noteList.querySelectorAll('.note-item').forEach(el => {
    el.addEventListener('click', () => openNote(parseInt(el.dataset.id)));
  });
}

function renderFolderList() {
  const allActive = currentFolderId === null;
  let html = `<div class="folder-item ${allActive ? 'active' : ''}" data-folder-id="" role="listitem">
    <span class="folder-icon">📂</span>
    <span class="folder-name">All Notes</span>
  </div>`;
  html += folders.map(f => {
    const isActive = currentFolderId === f.id;
    return `<div class="folder-item ${isActive ? 'active' : ''}" data-folder-id="${f.id}" role="listitem">
      <span class="folder-icon">📁</span>
      <span class="folder-name">${escapeHtml(f.name)}</span>
      <button class="btn-delete-folder" data-folder-id="${f.id}" title="Delete folder" aria-label="Delete folder ${escapeHtml(f.name)}">×</button>
    </div>`;
  }).join('');
  folderListEl.innerHTML = html;

  folderListEl.querySelectorAll('.folder-item').forEach(el => {
    el.addEventListener('click', e => {
      if (e.target.classList.contains('btn-delete-folder')) return;
      const raw = el.dataset.folderId;
      setFolderFilter(raw ? parseInt(raw) : null);
    });
  });

  folderListEl.querySelectorAll('.btn-delete-folder').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const fid = parseInt(btn.dataset.folderId);
      deleteFolder(fid);
    });
  });
}

function renderTagChips(note) {
  if (!note) { tagChipsEl.innerHTML = ''; return; }
  const trashed = !!note.is_trashed;
  tagChipsEl.innerHTML = (note.tags || []).map(t =>
    `<span class="tag-chip">${escapeHtml(t.name)}${trashed ? '' :
      `<button class="tag-chip-remove" data-tag-id="${t.id}" aria-label="Remove tag ${escapeHtml(t.name)}">×</button>`
    }</span>`
  ).join('');

  if (!trashed) {
    tagChipsEl.querySelectorAll('.tag-chip-remove').forEach(btn => {
      btn.addEventListener('click', () => removeTagFromNote(parseInt(btn.dataset.tagId)));
    });
  }
}

function updateTagDatalist() {
  const note = currentNote();
  const assignedIds = new Set((note && note.tags || []).map(t => t.id));
  tagDatalist.innerHTML = tags
    .filter(t => !assignedIds.has(t.id))
    .map(t => `<option value="${escapeHtml(t.name)}">`)
    .join('');
}

function populateFolderSelect() {
  // Rebuild folder options in the note editor dropdown
  let html = '<option value="">📁 No folder</option>';
  html += folders.map(f =>
    `<option value="${f.id}">${escapeHtml(f.name)}</option>`
  ).join('');
  noteFolderSelect.innerHTML = html;
}

function showEditor(show) {
  if (show) {
    editorContent.style.display = 'flex';
    editorWelcome.style.display = 'none';
  } else {
    editorContent.style.display = 'none';
    editorWelcome.style.display = '';
    currentNoteId = null;
    window.currentNoteId = null;
    images = [];
    if (imageBlocksEl) imageBlocksEl.innerHTML = '';
    if (imageToolbar) imageToolbar.style.display = 'none';
    if (fmtBar) fmtBar.style.display = 'none';
    setImageStatus('');
  }
}

function updateEditorToolbar(note) {
  if (!note) return;
  const trashed = !!note.is_trashed;
  const isConflict = !!note.conflict_of;

  btnPin.style.display = (trashed || isConflict) ? 'none' : '';
  btnArchive.style.display = (trashed || isConflict) ? 'none' : '';
  btnTrash.style.display = (trashed || isConflict) ? 'none' : '';
  btnRestore.style.display = trashed ? '' : 'none';
  btnDeletePermanent.style.display = trashed ? '' : 'none';
  if (btnHistory) btnHistory.style.display = (trashed || isConflict) ? 'none' : '';
  if (btnDeleteConflict) btnDeleteConflict.style.display = isConflict ? '' : 'none';

  btnPin.classList.toggle('active', !!note.is_pinned);
  btnPin.title = note.is_pinned ? 'Unpin note' : 'Pin note';

  btnArchive.classList.toggle('active', !!note.is_archived);
  btnArchive.title = note.is_archived ? 'Unarchive note' : 'Archive note';

  noteTitle.contentEditable = (trashed || isConflict) ? 'false' : 'true';
  noteBody.contentEditable = (trashed || isConflict) ? 'false' : 'true';
  if (noteBodyAfter) noteBodyAfter.contentEditable = (trashed || isConflict) ? 'false' : 'true';

  // Folder selector
  noteFolderSelect.value = note.folder_id != null ? String(note.folder_id) : '';
  noteFolderSelect.disabled = trashed || isConflict;

  // Tag bar
  tagInput.style.display = (trashed || isConflict) ? 'none' : '';
  renderTagChips(note);
  updateTagDatalist();

  // Image toolbar
  if (imageToolbar) imageToolbar.style.display = (trashed || isConflict) ? 'none' : '';
  // Formatting toolbar
  if (fmtBar) fmtBar.style.display = (trashed || isConflict) ? 'none' : '';
}

function openNote(id) {
  const note = notes.find(n => n.id === id);
  if (!note) return;

  if (autosaveTimer && currentNoteId && currentNoteId !== id) {
    clearTimeout(autosaveTimer);
    autosaveTimer = null;
    saveNote();
  }

  currentNoteId = id;
  window.currentNoteId = id;
  noteTitle.textContent = note.title;
  noteBody.innerHTML = note.body;
  if (noteBodyAfter) noteBodyAfter.innerHTML = note.body_after || '';
  showEditor(true);
  updateEditorToolbar(note);
  renderList();
  images = [];
  renderImageBlocks();
  setImageStatus('');
  loadImages(id);

  mainLayout.classList.add('editor-open');
}

function setAutosave(msg) {
  if (autosaveEl) autosaveEl.textContent = msg;
}

/* ===== API ===== */
async function apiRequest(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' }
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (res.status === 204) return null;
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function loadNotes() {
  try {
    const params = new URLSearchParams({ filter: currentFilter, sort: currentSort });
    if (searchQuery) params.set('q', searchQuery);
    if (currentFolderId !== null) params.set('folder_id', currentFolderId);
    notes = await apiRequest('GET', `/api/notes?${params}`);
    // Cache for offline use (only cache the default 'active' view with no filters)
    if (currentFilter === 'active' && !searchQuery && currentFolderId === null) {
      cacheNotes(notes);
    }
    renderList();
  } catch (e) {
    if (!navigator.onLine) {
      // Serve from IndexedDB cache when offline
      const cached = await getCachedNotes();
      if (cached.length > 0) {
        // Apply same filtering as the online view using cached data
        notes = cached.filter(n => {
          if (currentFilter === 'trashed') return !!n.is_trashed;
          if (currentFilter === 'archived') return !!n.is_archived && !n.is_trashed;
          return !n.is_archived && !n.is_trashed;
        });
        if (currentFolderId !== null) {
          notes = notes.filter(n => n.folder_id === currentFolderId);
        }
        if (searchQuery) {
          const q = searchQuery.toLowerCase();
          notes = notes.filter(n =>
            n.title.toLowerCase().includes(q) || n.body.toLowerCase().includes(q)
          );
        }
        renderList();
        console.log('[offline] serving', notes.length, 'note(s) from cache');
        return;
      }
    }
    console.error('Failed to load notes', e);
  }
}

async function loadFolders() {
  try {
    folders = await apiRequest('GET', '/api/folders');
    renderFolderList();
    populateFolderSelect();
  } catch (e) {
    console.error('Failed to load folders', e);
  }
}

async function loadTags() {
  try {
    tags = await apiRequest('GET', '/api/tags');
    updateTagDatalist();
  } catch (e) {
    console.error('Failed to load tags', e);
  }
}

async function createNote() {
  try {
    const payload = { title: '', body: '' };
    if (currentFolderId !== null) payload.folder_id = currentFolderId;
    const note = await apiRequest('POST', '/api/notes', payload);
    if (currentFilter !== 'active') {
      setFilter('active');
      return;
    }
    notes.unshift(note);
    renderList();
    openNote(note.id);
    noteTitle.focus();
  } catch (e) {
    console.error('Failed to create note', e);
  }
}

async function saveNote() {
  if (!currentNoteId) return;
  const note = currentNote();
  if (!note || note.is_trashed || note.conflict_of) return;
  isSaving = true;
  const title = noteTitle.textContent.trim();
  const body = noteBody.innerHTML;
  const body_after = noteBodyAfter ? noteBodyAfter.innerHTML : '';
  const is_pinned = note.is_pinned ? 1 : 0;
  const folder_id = note.folder_id != null ? note.folder_id : null;

  if (!navigator.onLine) {
    // Save to IndexedDB queue; will sync on reconnect
    await queueWrite(currentNoteId, title, body, body_after, is_pinned, folder_id);
    // Update local notes array so UI stays current
    const idx = notes.findIndex(n => n.id === currentNoteId);
    if (idx !== -1) {
      notes[idx] = { ...notes[idx], title, body, body_after, is_pinned, folder_id };
      await idbPut('cached_notes', { ...notes[idx], cached_at: Date.now() });
    }
    setSyncState(currentNoteId, 'local');
    renderList();
    isSaving = false;
    return;
  }

  setSyncState(currentNoteId, 'saving');
  try {
    const updated = await apiRequest('PUT', `/api/notes/${currentNoteId}`,
      { title, body, body_after, is_pinned, folder_id });
    const idx = notes.findIndex(n => n.id === currentNoteId);
    if (idx !== -1) notes[idx] = updated;
    // Remove from queue if it was previously queued
    await dequeueWrite(currentNoteId);
    await idbPut('cached_notes', { ...updated, cached_at: Date.now() });
    setSyncState(currentNoteId, 'synced');
    if (updated.conflict_note_id) showConflictBanner();
    renderList();
  } catch (e) {
    // Queue for retry
    await queueWrite(currentNoteId, title, body, body_after, is_pinned, folder_id);
    setSyncState(currentNoteId, 'failed');
    console.error('Save failed', e);
  } finally {
    isSaving = false;
  }
}

async function togglePin() {
  if (!currentNoteId) return;
  const note = currentNote();
  if (!note || note.is_trashed) return;
  const newPinned = note.is_pinned ? 0 : 1;
  clearTimeout(autosaveTimer);
  autosaveTimer = null;
  try {
    const title = noteTitle.textContent.trim();
    const body = noteBody.innerHTML;
    const body_after = noteBodyAfter ? noteBodyAfter.innerHTML : '';
    const folder_id = note.folder_id != null ? note.folder_id : null;
    const updated = await apiRequest('PUT', `/api/notes/${currentNoteId}`,
      { title, body, body_after, is_pinned: newPinned, folder_id });
    const idx = notes.findIndex(n => n.id === currentNoteId);
    if (idx !== -1) notes[idx] = updated;
    updateEditorToolbar(updated);
    renderList();
    setAutosave(newPinned ? 'Pinned' : 'Unpinned');
  } catch (e) {
    console.error('Pin toggle failed', e);
  }
}

async function toggleArchive() {
  if (!currentNoteId) return;
  const note = currentNote();
  if (!note || note.is_trashed) return;
  clearTimeout(autosaveTimer);
  autosaveTimer = null;
  try {
    await apiRequest('POST', `/api/notes/${currentNoteId}/archive`);
    notes = notes.filter(n => n.id !== currentNoteId);
    showEditor(false);
    mainLayout.classList.remove('editor-open');
    renderList();
    setAutosave('');
  } catch (e) {
    console.error('Archive toggle failed', e);
  }
}

async function trashNote() {
  if (!currentNoteId) return;
  const id = currentNoteId;
  clearTimeout(autosaveTimer);
  autosaveTimer = null;
  try {
    await apiRequest('DELETE', `/api/notes/${id}`);
    notes = notes.filter(n => n.id !== id);
    showEditor(false);
    mainLayout.classList.remove('editor-open');
    renderList();
    setAutosave('');
  } catch (e) {
    console.error('Trash failed', e);
  }
}

async function restoreNote() {
  if (!currentNoteId) return;
  const id = currentNoteId;
  try {
    await apiRequest('POST', `/api/notes/${id}/restore`);
    notes = notes.filter(n => n.id !== id);
    showEditor(false);
    mainLayout.classList.remove('editor-open');
    renderList();
    setAutosave('');
  } catch (e) {
    console.error('Restore failed', e);
  }
}

async function permanentDelete() {
  if (!currentNoteId) return;
  const id = currentNoteId;
  try {
    await apiRequest('DELETE', `/api/notes/${id}/permanent`);
    notes = notes.filter(n => n.id !== id);
    showEditor(false);
    mainLayout.classList.remove('editor-open');
    renderList();
    setAutosave('');
  } catch (e) {
    console.error('Permanent delete failed', e);
  }
}

async function changeNoteFolder(folderId) {
  if (!currentNoteId) return;
  const note = currentNote();
  if (!note || note.is_trashed) return;
  clearTimeout(autosaveTimer);
  autosaveTimer = null;
  try {
    const title = noteTitle.textContent.trim();
    const body = noteBody.innerHTML;
    const is_pinned = note.is_pinned ? 1 : 0;
    const updated = await apiRequest('PUT', `/api/notes/${currentNoteId}`,
      { title, body, is_pinned, folder_id: folderId || null });
    const idx = notes.findIndex(n => n.id === currentNoteId);
    if (idx !== -1) notes[idx] = updated;
    renderList();
    setAutosave('Saved');
  } catch (e) {
    console.error('Folder change failed', e);
  }
}

async function addTagToNote(name) {
  if (!currentNoteId || !name.trim()) return;
  const note = currentNote();
  if (!note || note.is_trashed) return;
  name = name.trim();

  // Find or create the tag
  let tag = tags.find(t => t.name.toLowerCase() === name.toLowerCase());
  if (!tag) {
    try {
      tag = await apiRequest('POST', '/api/tags', { name });
      tags.push(tag);
      tags.sort((a, b) => a.name.localeCompare(b.name));
    } catch (e) {
      console.error('Failed to create tag', e);
      return;
    }
  }

  // Check if already assigned
  if ((note.tags || []).some(t => t.id === tag.id)) return;

  const newTagIds = [...(note.tags || []).map(t => t.id), tag.id];
  try {
    const updatedTags = await apiRequest('PUT', `/api/notes/${currentNoteId}/tags`,
      { tag_ids: newTagIds });
    const idx = notes.findIndex(n => n.id === currentNoteId);
    if (idx !== -1) notes[idx] = { ...notes[idx], tags: updatedTags };
    renderTagChips(notes[idx]);
    updateTagDatalist();
    renderList();
  } catch (e) {
    console.error('Failed to set tags', e);
  }
}

async function removeTagFromNote(tagId) {
  if (!currentNoteId) return;
  const note = currentNote();
  if (!note || note.is_trashed) return;
  const newTagIds = (note.tags || []).filter(t => t.id !== tagId).map(t => t.id);
  try {
    const updatedTags = await apiRequest('PUT', `/api/notes/${currentNoteId}/tags`,
      { tag_ids: newTagIds });
    const idx = notes.findIndex(n => n.id === currentNoteId);
    if (idx !== -1) notes[idx] = { ...notes[idx], tags: updatedTags };
    renderTagChips(notes[idx]);
    updateTagDatalist();
    renderList();
  } catch (e) {
    console.error('Failed to remove tag', e);
  }
}

/* ===== Image handling ===== */
function setImageStatus(msg, isError) {
  imageUploadStatus.textContent = msg;
  imageUploadStatus.className = 'image-upload-status' + (isError ? ' error' : '');
}

function renderImageBlocks() {
  if (!imageBlocksEl) return;
  imageBlocksEl.innerHTML = '';
  const note = currentNote();
  const editable = note && !note.is_trashed;

  images.forEach((img, idx) => {
    const block = document.createElement('div');
    block.className = 'image-block';
    block.dataset.id = img.id;

    if (img.annotation_data) {
      // Show composite canvas preview when annotations exist
      const canvas = document.createElement('canvas');
      canvas.className = 'image-block-canvas';
      canvas.setAttribute('aria-label', escapeHtml(img.original_filename || 'Annotated image'));
      const srcImg = new Image();
      srcImg.onload = () => {
        if (typeof renderAnnotationPreview === 'function') {
          renderAnnotationPreview(canvas, srcImg, img.annotation_data);
        }
      };
      srcImg.src = img.url;
      block.appendChild(canvas);
    } else {
      const imgEl = document.createElement('img');
      imgEl.src = img.url;
      imgEl.alt = escapeHtml(img.original_filename || 'Image');
      imgEl.loading = 'lazy';
      block.appendChild(imgEl);
    }

    const controls = document.createElement('div');
    controls.className = 'image-block-controls';

    const btnUp = document.createElement('button');
    btnUp.className = 'btn-image-ctrl';
    btnUp.title = 'Move up';
    btnUp.setAttribute('aria-label', 'Move image up');
    btnUp.textContent = '↑';
    btnUp.disabled = idx === 0;
    btnUp.addEventListener('click', () => moveImage(img.id, -1));

    const btnDown = document.createElement('button');
    btnDown.className = 'btn-image-ctrl';
    btnDown.title = 'Move down';
    btnDown.setAttribute('aria-label', 'Move image down');
    btnDown.textContent = '↓';
    btnDown.disabled = idx === images.length - 1;
    btnDown.addEventListener('click', () => moveImage(img.id, 1));

    const btnDel = document.createElement('button');
    btnDel.className = 'btn-image-ctrl btn-danger';
    btnDel.title = 'Remove image';
    btnDel.setAttribute('aria-label', 'Remove image');
    btnDel.textContent = '🗑';
    btnDel.addEventListener('click', () => removeImage(img.id));

    const label = document.createElement('span');
    label.style.cssText = 'flex:1;font-size:11px;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-left:4px;';
    label.textContent = img.original_filename || '';

    controls.appendChild(btnUp);
    controls.appendChild(btnDown);
    if (editable) {
      const btnAnnotate = document.createElement('button');
      btnAnnotate.className = 'btn-image-ctrl';
      btnAnnotate.title = 'Annotate image';
      btnAnnotate.setAttribute('aria-label', 'Annotate image');
      btnAnnotate.textContent = '✏️';
      btnAnnotate.addEventListener('click', () => {
        if (typeof openAnnotationEditor === 'function') {
          openAnnotationEditor(currentNoteId, img.id, img.url, img.annotation_data);
        }
      });
      controls.appendChild(btnAnnotate);
    }
    controls.appendChild(btnDel);
    controls.appendChild(label);
    block.appendChild(controls);

    // Caption textarea (shown for all images; editable when note is not trashed)
    const captionArea = document.createElement('textarea');
    captionArea.className = 'image-caption';
    captionArea.placeholder = 'Add a caption or text…';
    captionArea.value = img.caption || '';
    captionArea.setAttribute('aria-label', 'Image caption');
    captionArea.readOnly = !editable;
    captionArea.addEventListener('blur', async () => {
      const newCaption = captionArea.value;
      if (newCaption === (img.caption || '')) return;
      try {
        const updated = await apiRequest('PUT',
          `/api/notes/${currentNoteId}/images/${img.id}`,
          { caption: newCaption });
        img.caption = updated.caption;
      } catch (e) {
        console.error('Failed to save image caption', e);
      }
    });
    block.appendChild(captionArea);

    // Section text: multi-line text area between this image and the next
    const sectionTextArea = document.createElement('textarea');
    sectionTextArea.className = 'image-section-text';
    sectionTextArea.placeholder = 'Add text after this image…';
    sectionTextArea.value = img.section_text || '';
    sectionTextArea.setAttribute('aria-label', 'Text after image');
    sectionTextArea.readOnly = !editable;
    sectionTextArea.addEventListener('blur', async () => {
      const newText = sectionTextArea.value;
      if (newText === (img.section_text || '')) return;
      try {
        const updated = await apiRequest('PUT',
          `/api/notes/${currentNoteId}/images/${img.id}`,
          { section_text: newText });
        img.section_text = updated.section_text;
      } catch (e) {
        console.error('Failed to save image section text', e);
      }
    });
    block.appendChild(sectionTextArea);

    imageBlocksEl.appendChild(block);
  });

  // Bottom toolbar: duplicate Add image / Camera buttons so the user
  // doesn't have to scroll back to the top after adding several images.
  if (editable && images.length > 0) {
    const bottomToolbar = document.createElement('div');
    bottomToolbar.className = 'image-toolbar image-toolbar-bottom';

    const btnAddBottom = document.createElement('button');
    btnAddBottom.className = 'btn-image-add';
    btnAddBottom.title = 'Upload image';
    btnAddBottom.setAttribute('aria-label', 'Upload image');
    btnAddBottom.textContent = '📎 Add image';
    btnAddBottom.addEventListener('click', () => inputUploadImage.click());

    const btnCamBottom = document.createElement('button');
    btnCamBottom.className = 'btn-image-add';
    btnCamBottom.title = 'Capture from camera';
    btnCamBottom.setAttribute('aria-label', 'Capture from camera');
    btnCamBottom.textContent = '📷 Camera';
    btnCamBottom.addEventListener('click', () => inputCameraCapture.click());

    bottomToolbar.appendChild(btnAddBottom);
    bottomToolbar.appendChild(btnCamBottom);
    imageBlocksEl.appendChild(bottomToolbar);
  }
}

async function loadImages(noteId) {
  try {
    images = await apiRequest('GET', `/api/notes/${noteId}/images`);
    renderImageBlocks();
  } catch (e) {
    console.error('Failed to load images', e);
  }
}

async function uploadImageFile(file) {
  if (!currentNoteId || !file) return;
  const note = currentNote();
  if (!note || note.is_trashed) return;

  setImageStatus('Uploading…');
  btnUploadImage.disabled = true;
  btnCameraCapture.disabled = true;

  const formData = new FormData();
  formData.append('image', file);

  try {
    const res = await fetch(`/api/notes/${currentNoteId}/images`, {
      method: 'POST',
      body: formData,
    });
    if (res.status === 413) {
      setImageStatus('Image too large (max 10 MB).', true);
      return;
    }
    if (res.status === 400) {
      setImageStatus('Unsupported file type. Please use JPEG, PNG, GIF, or WebP.', true);
      return;
    }
    if (!res.ok) {
      setImageStatus(`Upload failed (${res.status}). Please try again.`, true);
      return;
    }
    const img = await res.json();
    images.push(img);
    renderImageBlocks();
    setImageStatus('');
  } catch (e) {
    setImageStatus('Upload failed. Check your connection and try again.', true);
    console.error('Image upload failed', e);
  } finally {
    btnUploadImage.disabled = false;
    btnCameraCapture.disabled = false;
    inputUploadImage.value = '';
    inputCameraCapture.value = '';
  }
}

async function removeImage(imageId) {
  if (!currentNoteId) return;
  try {
    await apiRequest('DELETE', `/api/notes/${currentNoteId}/images/${imageId}`);
    images = images.filter(i => i.id !== imageId);
    renderImageBlocks();
    setImageStatus('');
  } catch (e) {
    setImageStatus('Could not remove image. Please try again.', true);
    console.error('Image delete failed', e);
  }
}

async function moveImage(imageId, delta) {
  const idx = images.findIndex(i => i.id === imageId);
  if (idx < 0) return;
  const newIdx = idx + delta;
  if (newIdx < 0 || newIdx >= images.length) return;

  // Swap in local array
  [images[idx], images[newIdx]] = [images[newIdx], images[idx]];
  renderImageBlocks();

  try {
    await apiRequest('PUT', `/api/notes/${currentNoteId}/images/reorder`,
      { image_ids: images.map(i => i.id) });
  } catch (e) {
    // Roll back on failure
    [images[idx], images[newIdx]] = [images[newIdx], images[idx]];
    renderImageBlocks();
    setImageStatus('Could not reorder images. Please try again.', true);
    console.error('Image reorder failed', e);
  }
}

async function createFolder(name) {
  name = name.trim();
  if (!name) return;
  try {
    const folder = await apiRequest('POST', '/api/folders', { name });
    folders.push(folder);
    folders.sort((a, b) => a.name.localeCompare(b.name));
    renderFolderList();
    populateFolderSelect();
  } catch (e) {
    console.error('Failed to create folder', e);
  }
}

async function deleteFolder(folderId) {
  try {
    await apiRequest('DELETE', `/api/folders/${folderId}`);
    folders = folders.filter(f => f.id !== folderId);
    // Unfile notes locally
    notes.forEach(n => { if (n.folder_id === folderId) n.folder_id = null; });
    if (currentFolderId === folderId) currentFolderId = null;
    renderFolderList();
    populateFolderSelect();
    renderList();
  } catch (e) {
    console.error('Failed to delete folder', e);
  }
}

/* ===== Version History ===== */
async function openHistoryPanel(noteId) {
  historyNoteId = noteId;
  historyList.innerHTML = '<div class="history-loading">Loading\u2026</div>';
  historyPanel.style.display = '';
  try {
    const versions = await apiRequest('GET', `/api/notes/${noteId}/versions`);
    if (versions.length === 0) {
      historyList.innerHTML = '<div class="history-empty">No versions saved yet.<br>Versions are created automatically when you update this note.</div>';
      return;
    }
    historyList.innerHTML = versions.map(v => {
      const d = new Date(v.saved_at.replace(' ', 'T') + 'Z');
      const label = d.toLocaleString('en-GB', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
      return `<div class="history-item" data-version-id="${v.id}">
        <div class="history-item-meta">
          <span class="history-item-date">${label}</span>
        </div>
        <div class="history-item-title">${escapeHtml(v.title || 'Untitled')}</div>
        <button class="btn-restore-version" data-version-id="${v.id}" aria-label="Restore version from ${label}">Restore</button>
      </div>`;
    }).join('');
    historyList.querySelectorAll('.btn-restore-version').forEach(btn => {
      btn.addEventListener('click', () => restoreVersion(noteId, parseInt(btn.dataset.versionId)));
    });
  } catch (e) {
    historyList.innerHTML = '<div class="history-empty">Failed to load version history.</div>';
    console.error('Failed to load history', e);
  }
}

function closeHistoryPanel() {
  historyPanel.style.display = 'none';
  historyNoteId = null;
}

async function restoreVersion(noteId, versionId) {
  if (!confirm('Restore this version? The current content will be saved as a new version first.')) return;
  try {
    const updated = await apiRequest('POST', `/api/notes/${noteId}/versions/${versionId}/restore`);
    const idx = notes.findIndex(n => n.id === noteId);
    if (idx !== -1) notes[idx] = updated;
    if (currentNoteId === noteId) {
      noteTitle.textContent = updated.title;
      noteBody.innerHTML = updated.body;
      if (noteBodyAfter) noteBodyAfter.innerHTML = updated.body_after || '';
      updateEditorToolbar(updated);
    }
    setAutosave('Restored \u2713');
    renderList();
    closeHistoryPanel();
  } catch (e) {
    console.error('Failed to restore version', e);
    alert('Failed to restore version. Please try again.');
  }
}

/* ===== Conflict Banner ===== */
function showConflictBanner() {
  if (conflictBanner) conflictBanner.style.display = '';
}

function hideConflictBanner() {
  if (conflictBanner) conflictBanner.style.display = 'none';
}

async function deleteConflictCopy() {
  if (!currentNoteId) return;
  const note = currentNote();
  if (!note || !note.conflict_of) return;
  const id = currentNoteId;
  try {
    await apiRequest('DELETE', `/api/conflicts/${id}`);
    notes = notes.filter(n => n.id !== id);
    showEditor(false);
    mainLayout.classList.remove('editor-open');
    renderList();
    setAutosave('');
  } catch (e) {
    console.error('Failed to delete conflict copy', e);
  }
}

/* ===== Autosave ===== */
function scheduleAutosave() {
  setAutosave('');
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(saveNote, 1500);
}

/* ===== Filter / Sort / Search ===== */
function setFilter(filter) {
  currentFilter = filter;
  // Hide folder section in Trash and Conflicts views
  folderSection.style.display = (filter === 'trashed' || filter === 'conflicts') ? 'none' : '';
  if (filter === 'trashed' || filter === 'conflicts') currentFolderId = null;

  filterTabs.forEach(t => {
    const isActive = t.dataset.filter === filter;
    t.classList.toggle('active', isActive);
    t.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });
  if (autosaveTimer && currentNoteId) {
    clearTimeout(autosaveTimer);
    autosaveTimer = null;
  }
  showEditor(false);
  mainLayout.classList.remove('editor-open');
  renderFolderList();
  loadNotes();
}

function setFolderFilter(folderId) {
  currentFolderId = folderId;
  renderFolderList();
  loadNotes();
}

function scheduleSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchQuery = searchInput.value.trim();
    loadNotes();
  }, SEARCH_DEBOUNCE_MS);
}

/* ===== Events ===== */
btnNew.addEventListener('click', createNote);

btnBack.addEventListener('click', () => {
  clearTimeout(autosaveTimer);
  autosaveTimer = null;
  const note = currentNote();
  if (currentNoteId && note && !note.is_trashed) saveNote();
  mainLayout.classList.remove('editor-open');
});

btnPin.addEventListener('click', togglePin);
btnArchive.addEventListener('click', toggleArchive);
btnTrash.addEventListener('click', trashNote);
btnRestore.addEventListener('click', restoreNote);

if (btnExportPdf) {
  btnExportPdf.addEventListener('click', () => {
    if (!currentNoteId) return;
    window.open(`/api/notes/${currentNoteId}/export.pdf`, '_blank');
  });
}

btnDeletePermanent.addEventListener('click', () => {
  if (!currentNoteId) return;
  dialogOverlay.classList.add('visible');
});

btnCancelDelete.addEventListener('click', () => {
  dialogOverlay.classList.remove('visible');
});

btnConfirmDelete.addEventListener('click', async () => {
  dialogOverlay.classList.remove('visible');
  await permanentDelete();
});

dialogOverlay.addEventListener('click', e => {
  if (e.target === dialogOverlay) dialogOverlay.classList.remove('visible');
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && dialogOverlay.classList.contains('visible')) {
    dialogOverlay.classList.remove('visible');
  }
});

noteTitle.addEventListener('input', scheduleAutosave);
noteBody.addEventListener('input', scheduleAutosave);
if (noteBodyAfter) noteBodyAfter.addEventListener('input', scheduleAutosave);

noteTitle.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    e.preventDefault();
    noteBody.focus();
  }
});

filterTabs.forEach(tab => {
  tab.addEventListener('click', () => setFilter(tab.dataset.filter));
});

searchInput.addEventListener('input', scheduleSearch);

// Clear search on Escape
searchInput.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    searchInput.value = '';
    searchQuery = '';
    loadNotes();
  }
});

sortSelect.addEventListener('change', () => {
  currentSort = sortSelect.value;
  loadNotes();
});

noteFolderSelect.addEventListener('change', () => {
  const raw = noteFolderSelect.value;
  changeNoteFolder(raw ? parseInt(raw) : null);
});

// New folder creation
btnNewFolder.addEventListener('click', () => {
  newFolderForm.style.display = newFolderForm.style.display === 'none' ? '' : 'none';
  if (newFolderForm.style.display !== 'none') {
    newFolderInput.value = '';
    newFolderInput.focus();
  }
});

newFolderInput.addEventListener('keydown', async e => {
  if (e.key === 'Enter') {
    const name = newFolderInput.value.trim();
    if (name) await createFolder(name);
    newFolderForm.style.display = 'none';
    newFolderInput.value = '';
  } else if (e.key === 'Escape') {
    newFolderForm.style.display = 'none';
    newFolderInput.value = '';
  }
});

// Tag input — add tag on Enter or comma
tagInput.addEventListener('keydown', async e => {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault();
    const name = tagInput.value.replace(',', '').trim();
    if (name) await addTagToNote(name);
    tagInput.value = '';
  } else if (e.key === 'Escape') {
    tagInput.value = '';
  }
});

/* ===== Image upload events ===== */
btnUploadImage.addEventListener('click', () => inputUploadImage.click());
btnCameraCapture.addEventListener('click', () => inputCameraCapture.click());

inputUploadImage.addEventListener('change', async () => {
  const file = inputUploadImage.files[0];
  if (file) await uploadImageFile(file);
});

inputCameraCapture.addEventListener('change', async () => {
  const file = inputCameraCapture.files[0];
  if (file) await uploadImageFile(file);
});

/* ===== Offline detection ===== */
function updateOnlineStatus() {
  offlineBanner.classList.toggle('visible', !navigator.onLine);
  if (navigator.onLine) {
    flushQueue().then(() => renderList());
  }
}
window.addEventListener('online', updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);
updateOnlineStatus();

/* ===== Service Worker ===== */
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(console.error);
  });
}

/* ===== Init ===== */
showEditor(false);
loadFolders();
loadTags();
loadNotes();
if (typeof initAnnotationEditor === 'function') initAnnotationEditor();

// Flush any pending writes on startup (if online)
if (navigator.onLine) {
  getPendingWrites().then(pending => {
    if (pending.length > 0) {
      console.log('[sync] found', pending.length, 'pending write(s) on startup');
      // Mark those notes as 'local' initially
      pending.forEach(w => syncStates.set(w.note_id, 'local'));
      flushQueue().then(() => renderList());
    }
  }).catch(console.error);
}

// Autosave indicator click — retry failed syncs
if (autosaveEl) {
  autosaveEl.addEventListener('click', () => {
    if (autosaveEl.dataset.syncState === 'failed') {
      flushRetryCount = 0;
      flushInProgress = false;
      flushQueue().then(() => renderList());
    }
  });
}

/* ===== History panel events ===== */
if (btnHistory) {
  btnHistory.addEventListener('click', () => {
    if (currentNoteId) openHistoryPanel(currentNoteId);
  });
}

if (btnCloseHistory) {
  btnCloseHistory.addEventListener('click', closeHistoryPanel);
}

if (historyPanel) {
  historyPanel.addEventListener('click', e => {
    if (e.target === historyPanel) closeHistoryPanel();
  });
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && historyPanel && historyPanel.style.display !== 'none') {
    closeHistoryPanel();
  }
});

/* ===== Conflict banner events ===== */
if (btnViewConflicts) {
  btnViewConflicts.addEventListener('click', () => {
    hideConflictBanner();
    setFilter('conflicts');
  });
}

if (btnDismissConflictBanner) {
  btnDismissConflictBanner.addEventListener('click', hideConflictBanner);
}

if (btnDeleteConflict) {
  btnDeleteConflict.addEventListener('click', deleteConflictCopy);
}

/* ===== Formatting toolbar ===== */
// Track which editable area is currently focused for formatting
let _fmtTarget = null;
[noteBody, noteBodyAfter].forEach(el => {
  if (!el) return;
  el.addEventListener('focus', () => { _fmtTarget = el; });
});

function _applyFmt(cmd, value) {
  // Restore focus to the note body before executing command
  if (_fmtTarget) _fmtTarget.focus();
  else noteBody.focus();
  document.execCommand(cmd, false, value || null);
  scheduleAutosave();
  _updateFmtActiveState();
}

function _updateFmtActiveState() {
  if (fmtBtnBold)   fmtBtnBold.classList.toggle('active', document.queryCommandState('bold'));
  if (fmtBtnItalic) fmtBtnItalic.classList.toggle('active', document.queryCommandState('italic'));
  if (fmtBtnUnder)  fmtBtnUnder.classList.toggle('active', document.queryCommandState('underline'));
  if (fmtBtnStrike) fmtBtnStrike.classList.toggle('active', document.queryCommandState('strikeThrough'));
  if (fmtBtnUl)     fmtBtnUl.classList.toggle('active', document.queryCommandState('insertUnorderedList'));
  if (fmtBtnOl)     fmtBtnOl.classList.toggle('active', document.queryCommandState('insertOrderedList'));
}

document.addEventListener('selectionchange', _updateFmtActiveState);

if (fmtBtnBold)   fmtBtnBold.addEventListener('mousedown',   e => { e.preventDefault(); _applyFmt('bold'); });
if (fmtBtnItalic) fmtBtnItalic.addEventListener('mousedown', e => { e.preventDefault(); _applyFmt('italic'); });
if (fmtBtnUnder)  fmtBtnUnder.addEventListener('mousedown',  e => { e.preventDefault(); _applyFmt('underline'); });
if (fmtBtnStrike) fmtBtnStrike.addEventListener('mousedown', e => { e.preventDefault(); _applyFmt('strikeThrough'); });
if (fmtBtnUl)     fmtBtnUl.addEventListener('mousedown',     e => { e.preventDefault(); _applyFmt('insertUnorderedList'); });
if (fmtBtnOl)     fmtBtnOl.addEventListener('mousedown',     e => { e.preventDefault(); _applyFmt('insertOrderedList'); });
if (fmtBtnClear)  fmtBtnClear.addEventListener('mousedown',  e => { e.preventDefault(); _applyFmt('removeFormat'); });

if (fmtColor) {
  fmtColor.addEventListener('input', () => _applyFmt('foreColor', fmtColor.value));
}

if (fmtHighlight) {
  fmtHighlight.addEventListener('input', () => _applyFmt('backColor', fmtHighlight.value));
}

if (fmtSize) {
  fmtSize.addEventListener('change', () => {
    if (!fmtSize.value) return;
    _applyFmt('fontSize', fmtSize.value);
    fmtSize.value = '';
  });
}
