/* ===== State ===== */
let notes = [];
let currentNoteId = null;
let autosaveTimer = null;
let isSaving = false;

/* ===== DOM refs ===== */
const noteList = document.getElementById('note-list');
const noteTitle = document.getElementById('note-title');
const noteBody = document.getElementById('note-body');
const autosaveEl = document.getElementById('autosave-indicator');
const offlineBanner = document.getElementById('offline-banner');
const btnNew = document.getElementById('btn-new');
const btnDelete = document.getElementById('btn-delete');
const btnBack = document.getElementById('btn-back');
const mainLayout = document.querySelector('.main-layout');
const editorPane = document.querySelector('.editor-pane');
const editorContent = document.getElementById('editor-content');
const editorWelcome = document.getElementById('editor-welcome');
const dialogOverlay = document.getElementById('dialog-overlay');
const btnCancelDelete = document.getElementById('btn-cancel-delete');
const btnConfirmDelete = document.getElementById('btn-confirm-delete');

/* ===== Helpers ===== */
function formatDate(dateStr) {
  const d = new Date(dateStr.replace(' ', 'T') + (dateStr.includes('T') ? '' : 'Z'));
  const now = new Date();
  const diff = now - d;
  const dayMs = 86400000;
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const itemDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const dayDiff = Math.round((today - itemDay) / dayMs);

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

/* ===== Rendering ===== */
function renderList() {
  if (notes.length === 0) {
    noteList.innerHTML = `
      <div class="empty-state">
        <div class="icon">📝</div>
        <p>No notes yet.<br>Tap <strong>+</strong> to create one.</p>
      </div>`;
    return;
  }
  noteList.innerHTML = notes.map(n => `
    <div class="note-item ${n.id === currentNoteId ? 'active' : ''}" data-id="${n.id}">
      <div class="note-item-title">${escapeHtml(getTitle(n))}</div>
      <div class="note-item-subtitle">${escapeHtml(getSubtitle(n))}</div>
      <div class="note-item-date">${formatDate(n.updated_at)}</div>
    </div>`).join('');

  noteList.querySelectorAll('.note-item').forEach(el => {
    el.addEventListener('click', () => openNote(parseInt(el.dataset.id)));
  });
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function showEditor(show) {
  if (show) {
    editorContent.style.display = '';
    editorWelcome.style.display = 'none';
    btnDelete.style.display = '';
  } else {
    editorContent.style.display = 'none';
    editorWelcome.style.display = '';
    btnDelete.style.display = 'none';
    currentNoteId = null;
  }
}

function openNote(id) {
  const note = notes.find(n => n.id === id);
  if (!note) return;
  currentNoteId = id;
  noteTitle.textContent = note.title;
  noteBody.textContent = note.body;
  showEditor(true);
  renderList(); // update active state

  // Mobile: show editor pane
  mainLayout.classList.add('editor-open');
}

function setAutosave(msg) {
  autosaveEl.textContent = msg;
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
  return res.json();
}

async function loadNotes() {
  try {
    notes = await apiRequest('GET', '/api/notes');
    renderList();
  } catch (e) {
    console.error('Failed to load notes', e);
  }
}

async function createNote() {
  try {
    const note = await apiRequest('POST', '/api/notes', { title: '', body: '' });
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
  isSaving = true;
  setAutosave('Saving…');
  const title = noteTitle.textContent.trim();
  const body = noteBody.textContent;
  try {
    const updated = await apiRequest('PUT', `/api/notes/${currentNoteId}`, { title, body });
    // Update local cache
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

async function deleteCurrentNote() {
  if (!currentNoteId) return;
  const id = currentNoteId;
  try {
    await apiRequest('DELETE', `/api/notes/${id}`);
    notes = notes.filter(n => n.id !== id);
    showEditor(false);
    mainLayout.classList.remove('editor-open');
    renderList();
    setAutosave('');
  } catch (e) {
    console.error('Delete failed', e);
  }
}

/* ===== Autosave ===== */
function scheduleAutosave() {
  setAutosave('');
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(saveNote, 1500);
}

/* ===== Events ===== */
btnNew.addEventListener('click', createNote);

btnBack.addEventListener('click', () => {
  // Flush any pending save immediately
  clearTimeout(autosaveTimer);
  if (currentNoteId) saveNote();
  mainLayout.classList.remove('editor-open');
});

btnDelete.addEventListener('click', () => {
  if (!currentNoteId) return;
  dialogOverlay.classList.add('visible');
});

btnCancelDelete.addEventListener('click', () => {
  dialogOverlay.classList.remove('visible');
});

btnConfirmDelete.addEventListener('click', async () => {
  dialogOverlay.classList.remove('visible');
  await deleteCurrentNote();
});

// Close dialog on overlay click
dialogOverlay.addEventListener('click', e => {
  if (e.target === dialogOverlay) dialogOverlay.classList.remove('visible');
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
