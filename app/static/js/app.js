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
let pendingNoteIds = new Set();   // note IDs with unsynced local writes
let flushInProgress = false;
let flushRetryDelay = INITIAL_FLUSH_RETRY_DELAY_MS;

/* ===== Constants ===== */
const DAY_MS = 86400000;
const SEARCH_DEBOUNCE_MS = 300;
const INITIAL_FLUSH_RETRY_DELAY_MS = 2000;
const MAX_FLUSH_RETRY_DELAY_MS = 60000;

/* ===== DOM refs ===== */
const noteList = document.getElementById('note-list');
const noteTitle = document.getElementById('note-title');
const noteBody = document.getElementById('note-body');
const autosaveEl = document.getElementById('autosave-indicator');
const offlineBanner = document.getElementById('offline-banner');
const btnNew = document.getElementById('btn-new');
const btnBack = document.getElementById('btn-back');
const btnPin = document.getElementById('btn-pin');
const btnArchive = document.getElementById('btn-archive');
const btnTrash = document.getElementById('btn-trash');
const btnRestore = document.getElementById('btn-restore');
const btnDeletePermanent = document.getElementById('btn-delete-permanent');
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

/* ===== Helpers ===== */
function formatDate(dateStr) {
  const d = new Date(dateStr.replace(' ', 'T') + (dateStr.includes('T') ? '' : 'Z'));
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const itemDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const dayDiff = Math.round((today - itemDay) / DAY_MS);

  if (dayDiff === 0) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } else if (dayDiff === 1) {
    return 'Yesterday';
  } else if (dayDiff < 7) {
    return d.toLocaleDateString([], { weekday: 'short' });
  } else {
    return d.toLocaleDateString([], { day: 'numeric', month: 'short' });
  }
}

function getTitle(note) {
  return note.title.trim() || 'Untitled';
}

function getSubtitle(note) {
  const first = note.body.split('\n')[0];
  return first.trim() || '—';
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function currentNote() {
  return notes.find(n => n.id === currentNoteId) || null;
}

/* ===== IndexedDB offline write queue ===== */
const _DB_NAME = 'notes-pwa';
const _DB_VERSION = 1;
const _STORE = 'pending_writes';

function _openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(_DB_NAME, _DB_VERSION);
    req.onupgradeneeded = e => {
      e.target.result.createObjectStore(_STORE, { keyPath: 'note_id' });
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = e => reject(e.target.error);
  });
}

async function _queueWrite(note_id, title, body, is_pinned, folder_id) {
  const db = await _openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(_STORE, 'readwrite');
    tx.objectStore(_STORE).put({
      note_id, title, body,
      is_pinned, folder_id,
      queued_at: Date.now(),
    });
    tx.oncomplete = resolve;
    tx.onerror = e => reject(e.target.error);
  });
}

async function _getPendingWrites() {
  const db = await _openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(_STORE, 'readonly');
    const req = tx.objectStore(_STORE).getAll();
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = e => reject(e.target.error);
  });
}

async function _removePendingWrite(note_id) {
  const db = await _openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(_STORE, 'readwrite');
    tx.objectStore(_STORE).delete(note_id);
    tx.oncomplete = resolve;
    tx.onerror = e => reject(e.target.error);
  });
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
    const pendingBadge = pendingNoteIds.has(n.id)
      ? '<span class="note-pending-badge" title="Unsynced local changes" aria-label="Unsynced">●</span>'
      : '';
    return `
    <div class="note-item ${n.id === currentNoteId ? 'active' : ''}" data-id="${n.id}" role="listitem">
      <div class="note-item-header">
        <div class="note-item-title">${escapeHtml(getTitle(n))}</div>
        ${n.is_pinned ? '<span class="note-pin-badge" aria-label="Pinned">📌</span>' : ''}
        ${pendingBadge}
      </div>
      <div class="note-item-subtitle">${escapeHtml(getSubtitle(n))}</div>
      ${tagHtml}
      <div class="note-item-date">Edited ${formatDate(n.updated_at)}</div>
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
    images = [];
    if (imageBlocksEl) imageBlocksEl.innerHTML = '';
    if (imageToolbar) imageToolbar.style.display = 'none';
    setImageStatus('');
  }
}

function updateEditorToolbar(note) {
  if (!note) return;
  const trashed = !!note.is_trashed;

  btnPin.style.display = trashed ? 'none' : '';
  btnArchive.style.display = trashed ? 'none' : '';
  btnTrash.style.display = trashed ? 'none' : '';
  btnRestore.style.display = trashed ? '' : 'none';
  btnDeletePermanent.style.display = trashed ? '' : 'none';

  btnPin.classList.toggle('active', !!note.is_pinned);
  btnPin.title = note.is_pinned ? 'Unpin note' : 'Pin note';

  btnArchive.classList.toggle('active', !!note.is_archived);
  btnArchive.title = note.is_archived ? 'Unarchive note' : 'Archive note';

  noteTitle.contentEditable = trashed ? 'false' : 'true';
  noteBody.contentEditable = trashed ? 'false' : 'true';

  // Folder selector
  noteFolderSelect.value = note.folder_id != null ? String(note.folder_id) : '';
  noteFolderSelect.disabled = trashed;

  // Tag bar
  tagInput.style.display = trashed ? 'none' : '';
  renderTagChips(note);
  updateTagDatalist();

  // Image toolbar
  if (imageToolbar) imageToolbar.style.display = trashed ? 'none' : '';
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
  noteTitle.textContent = note.title;
  noteBody.textContent = note.body;
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

/**
 * Sets the sync state indicator in the editor header.
 * @param {'synced'|'saving'|'local'|'failed'} state
 */
function setSyncState(state) {
  if (!autosaveEl) return;
  autosaveEl.dataset.syncState = state;
  switch (state) {
    case 'saving':  autosaveEl.textContent = 'Saving…'; break;
    case 'synced':  autosaveEl.textContent = 'Saved ✓'; break;
    case 'local':   autosaveEl.textContent = '⚠ Queued offline'; break;
    case 'failed':  autosaveEl.textContent = '✗ Failed — tap to retry'; break;
    default:        autosaveEl.textContent = ''; break;
  }
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
    renderList();
  } catch (e) {
    console.error('Failed to load notes', e);
  }
}

/* ===== Offline sync queue flush ===== */
async function flushQueue() {
  if (flushInProgress || !navigator.onLine) return;
  let pending;
  try {
    pending = await _getPendingWrites();
  } catch (e) {
    console.error('[Sync] Could not read pending writes', e);
    return;
  }
  if (pending.length === 0) return;

  flushInProgress = true;
  console.info('[Sync] Flushing', pending.length, 'pending write(s)');

  // Sort by queued_at ascending so oldest writes go first
  pending.sort((a, b) => a.queued_at - b.queued_at);

  for (const entry of pending) {
    try {
      const { note_id, title, body, is_pinned, folder_id } = entry;
      const updated = await apiRequest('PUT', `/api/notes/${note_id}`,
        { title, body, is_pinned: is_pinned || 0, folder_id: folder_id || null });

      const idx = notes.findIndex(n => n.id === note_id);
      if (idx !== -1) notes[idx] = updated;

      await _removePendingWrite(note_id);
      pendingNoteIds.delete(note_id);
      if (currentNoteId === note_id) setSyncState('synced');
      renderList();
      flushRetryDelay = INITIAL_FLUSH_RETRY_DELAY_MS; // reset backoff after success
    } catch (e) {
      console.error('[Sync] Flush failed for note', entry.note_id, e);
      if (currentNoteId === entry.note_id) setSyncState('failed');
      flushInProgress = false;
      // Exponential backoff before retrying the queue
      setTimeout(flushQueue, flushRetryDelay);
      flushRetryDelay = Math.min(flushRetryDelay * 2, MAX_FLUSH_RETRY_DELAY_MS);
      return;
    }
  }

  flushInProgress = false;
  console.info('[Sync] Queue flushed successfully');
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
  if (!note || note.is_trashed) return;
  isSaving = true;

  const title = noteTitle.textContent.trim();
  const body = noteBody.textContent;
  const is_pinned = note.is_pinned ? 1 : 0;
  const folder_id = note.folder_id != null ? note.folder_id : null;

  if (!navigator.onLine) {
    // Store write in IndexedDB; will flush on reconnect
    try {
      await _queueWrite(currentNoteId, title, body, is_pinned, folder_id);
      pendingNoteIds.add(currentNoteId);
      setSyncState('local');
      // Update local notes array so the list reflects edits while offline
      const idx = notes.findIndex(n => n.id === currentNoteId);
      if (idx !== -1) {
        notes[idx] = { ...notes[idx], title, body, is_pinned, folder_id };
      }
      renderList();
    } catch (e) {
      console.error('[Sync] Failed to queue write', e);
      setSyncState('failed');
    }
    isSaving = false;
    return;
  }

  setSyncState('saving');
  try {
    const updated = await apiRequest('PUT', `/api/notes/${currentNoteId}`,
      { title, body, is_pinned, folder_id });
    const idx = notes.findIndex(n => n.id === currentNoteId);
    if (idx !== -1) notes[idx] = updated;
    // Remove from pending queue if it was queued offline
    await _removePendingWrite(currentNoteId);
    pendingNoteIds.delete(currentNoteId);
    setSyncState('synced');
    renderList();
  } catch (e) {
    setSyncState('failed');
    // Queue for retry
    try {
      await _queueWrite(currentNoteId, title, body, is_pinned, folder_id);
      pendingNoteIds.add(currentNoteId);
    } catch (qe) {
      console.error('[Sync] Failed to queue write after error', qe);
    }
    renderList();
    console.error('[Sync] Save failed', e);
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
    const body = noteBody.textContent;
    const folder_id = note.folder_id != null ? note.folder_id : null;
    const updated = await apiRequest('PUT', `/api/notes/${currentNoteId}`,
      { title, body, is_pinned: newPinned, folder_id });
    const idx = notes.findIndex(n => n.id === currentNoteId);
    if (idx !== -1) notes[idx] = updated;
    updateEditorToolbar(updated);
    renderList();
    setSyncState('synced');
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
    const body = noteBody.textContent;
    const is_pinned = note.is_pinned ? 1 : 0;
    const updated = await apiRequest('PUT', `/api/notes/${currentNoteId}`,
      { title, body, is_pinned, folder_id: folderId || null });
    const idx = notes.findIndex(n => n.id === currentNoteId);
    if (idx !== -1) notes[idx] = updated;
    renderList();
    setSyncState('synced');
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
    imageBlocksEl.appendChild(block);
  });
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

/* ===== Autosave ===== */
function scheduleAutosave() {
  setSyncState('');
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(saveNote, 1500);
}

/* ===== Filter / Sort / Search ===== */
function setFilter(filter) {
  currentFilter = filter;
  // Hide folder section in Trash view
  folderSection.style.display = filter === 'trashed' ? 'none' : '';
  if (filter === 'trashed') currentFolderId = null;

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
}
window.addEventListener('online', () => {
  updateOnlineStatus();
  // Flush any queued offline writes when connectivity is restored
  flushQueue();
});
window.addEventListener('offline', updateOnlineStatus);
updateOnlineStatus();

/* ===== Service Worker ===== */
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(console.error);
  });
}

/* ===== Init ===== */
showEditor(false);
loadFolders();
loadTags();
loadNotes();
if (typeof initAnnotationEditor === 'function') initAnnotationEditor();

// Load pending note IDs from IndexedDB so list badges show on startup
_getPendingWrites().then(pending => {
  pending.forEach(p => pendingNoteIds.add(p.note_id));
  if (pendingNoteIds.size > 0) renderList();
  // Flush any pending writes if we're already online
  if (navigator.onLine) flushQueue();
}).catch(e => console.error('[Sync] Could not load pending writes on init', e));

// Retry sync when user taps the failed indicator
if (autosaveEl) {
  autosaveEl.addEventListener('click', () => {
    if (autosaveEl.dataset.syncState === 'failed') {
      flushQueue();
    }
  });
}
