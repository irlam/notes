/* ===== State ===== */
let notes = [];
let folders = [];
let tags = [];
let currentNoteId = null;
let autosaveTimer = null;
let searchTimer = null;
let isSaving = false;
let currentFilter = 'active';
let currentFolderId = null;   // null = all, number = filter by folder
let currentSort = 'updated_desc';
let searchQuery = '';

/* ===== Constants ===== */
const DAY_MS = 86400000;
const SEARCH_DEBOUNCE_MS = 300;

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
    return `
    <div class="note-item ${n.id === currentNoteId ? 'active' : ''}" data-id="${n.id}" role="listitem">
      <div class="note-item-header">
        <div class="note-item-title">${escapeHtml(getTitle(n))}</div>
        ${n.is_pinned ? '<span class="note-pin-badge" aria-label="Pinned">📌</span>' : ''}
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
    renderList();
  } catch (e) {
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
  if (!note || note.is_trashed) return;
  isSaving = true;
  setAutosave('Saving…');
  const title = noteTitle.textContent.trim();
  const body = noteBody.textContent;
  const is_pinned = note.is_pinned ? 1 : 0;
  const folder_id = note.folder_id != null ? note.folder_id : null;
  try {
    const updated = await apiRequest('PUT', `/api/notes/${currentNoteId}`,
      { title, body, is_pinned, folder_id });
    const idx = notes.findIndex(n => n.id === currentNoteId);
    if (idx !== -1) notes[idx] = updated;
    renderList();
    setAutosave('Saved');
  } catch (e) {
    setAutosave('Save failed');
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
    const body = noteBody.textContent;
    const folder_id = note.folder_id != null ? note.folder_id : null;
    const updated = await apiRequest('PUT', `/api/notes/${currentNoteId}`,
      { title, body, is_pinned: newPinned, folder_id });
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
    const body = noteBody.textContent;
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
  setAutosave('');
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

/* ===== Offline detection ===== */
function updateOnlineStatus() {
  offlineBanner.classList.toggle('visible', !navigator.onLine);
}
window.addEventListener('online', updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);
updateOnlineStatus();

/* ===== Service Worker ===== */
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js').catch(console.error);
  });
}

/* ===== Init ===== */
showEditor(false);
loadFolders();
loadTags();
loadNotes();
