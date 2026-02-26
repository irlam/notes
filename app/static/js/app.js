/* ===== State ===== */
let notes = [];
let currentNoteId = null;
let autosaveTimer = null;
let isSaving = false;
let currentFilter = 'active';

/* ===== Constants ===== */
const DAY_MS = 86400000;

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
    noteList.innerHTML = `
      <div class="empty-state">
        <div class="icon">📝</div>
        <p>${msgs[currentFilter] || msgs.active}</p>
      </div>`;
    return;
  }
  noteList.innerHTML = notes.map(n => `
    <div class="note-item ${n.id === currentNoteId ? 'active' : ''}" data-id="${n.id}" role="listitem">
      <div class="note-item-header">
        <div class="note-item-title">${escapeHtml(getTitle(n))}</div>
        ${n.is_pinned ? '<span class="note-pin-badge" aria-label="Pinned">📌</span>' : ''}
      </div>
      <div class="note-item-subtitle">${escapeHtml(getSubtitle(n))}</div>
      <div class="note-item-date">Edited ${formatDate(n.updated_at)}</div>
    </div>`).join('');

  noteList.querySelectorAll('.note-item').forEach(el => {
    el.addEventListener('click', () => openNote(parseInt(el.dataset.id)));
  });
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

  // Show/hide buttons based on trashed state
  btnPin.style.display = trashed ? 'none' : '';
  btnArchive.style.display = trashed ? 'none' : '';
  btnTrash.style.display = trashed ? 'none' : '';
  btnRestore.style.display = trashed ? '' : 'none';
  btnDeletePermanent.style.display = trashed ? '' : 'none';

  // Pin active state
  btnPin.classList.toggle('active', !!note.is_pinned);
  btnPin.title = note.is_pinned ? 'Unpin note' : 'Pin note';

  // Archive active state
  btnArchive.classList.toggle('active', !!note.is_archived);
  btnArchive.title = note.is_archived ? 'Unarchive note' : 'Archive note';

  // Make editor read-only in trash
  noteTitle.contentEditable = trashed ? 'false' : 'true';
  noteBody.contentEditable = trashed ? 'false' : 'true';
}

function openNote(id) {
  const note = notes.find(n => n.id === id);
  if (!note) return;

  // Flush any pending save for previous note before switching
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

  // Mobile: show editor pane
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
    notes = await apiRequest('GET', `/api/notes?filter=${currentFilter}`);
    renderList();
  } catch (e) {
    console.error('Failed to load notes', e);
  }
}

async function createNote() {
  try {
    const note = await apiRequest('POST', '/api/notes', { title: '', body: '' });
    // Switch to active filter so new note is visible
    if (currentFilter !== 'active') {
      setFilter('active');
      return; // loadNotes will re-render; open after load
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
  if (!note || note.is_trashed) return; // don't save trashed notes
  isSaving = true;
  setAutosave('Saving…');
  const title = noteTitle.textContent.trim();
  const body = noteBody.textContent;
  const is_pinned = note ? (note.is_pinned ? 1 : 0) : 0;
  try {
    const updated = await apiRequest('PUT', `/api/notes/${currentNoteId}`, { title, body, is_pinned });
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
    const updated = await apiRequest('PUT', `/api/notes/${currentNoteId}`, { title, body, is_pinned: newPinned });
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
    const updated = await apiRequest('POST', `/api/notes/${currentNoteId}/archive`);
    // Note moves out of current filter view
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

/* ===== Autosave ===== */
function scheduleAutosave() {
  setAutosave('');
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(saveNote, 1500);
}

/* ===== Filter ===== */
function setFilter(filter) {
  currentFilter = filter;
  filterTabs.forEach(t => {
    const isActive = t.dataset.filter === filter;
    t.classList.toggle('active', isActive);
    t.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });
  // Close editor when switching filters
  if (autosaveTimer && currentNoteId) {
    clearTimeout(autosaveTimer);
    autosaveTimer = null;
  }
  showEditor(false);
  mainLayout.classList.remove('editor-open');
  loadNotes();
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

// Close dialog on overlay click
dialogOverlay.addEventListener('click', e => {
  if (e.target === dialogOverlay) dialogOverlay.classList.remove('visible');
});

// Close dialog on Escape key
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && dialogOverlay.classList.contains('visible')) {
    dialogOverlay.classList.remove('visible');
  }
});

noteTitle.addEventListener('input', scheduleAutosave);
noteBody.addEventListener('input', scheduleAutosave);

// Prevent newline in title (Enter moves to body)
noteTitle.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    e.preventDefault();
    noteBody.focus();
  }
});

// Filter tab clicks
filterTabs.forEach(tab => {
  tab.addEventListener('click', () => setFilter(tab.dataset.filter));
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
loadNotes();
