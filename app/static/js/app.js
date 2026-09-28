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
    const req = indexedDB.open('notes-pwa', 2);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('pending_writes')) {
        db.createObjectStore('pending_writes', { keyPath: 'note_id' });
      }
      if (!db.objectStoreNames.contains('cached_notes')) {
        db.createObjectStore('cached_notes', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('cached_images')) {
        db.createObjectStore('cached_images', { keyPath: 'cache_key' });
      }
      if (!db.objectStoreNames.contains('pending_ops')) {
        const ops = db.createObjectStore('pending_ops', { keyPath: 'op_id', autoIncrement: true });
        ops.createIndex('queued_at', 'queued_at');
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

async function queueOperation(operation) {
  await idbPut('pending_ops', { ...operation, queued_at: Date.now() });
  await updateGlobalSyncStatus();
}

async function getPendingOperations() {
  return idbGetAll('pending_ops');
}

async function updateGlobalSyncStatus(state) {
  const el = document.getElementById('sync-banner');
  if (!el) return;
  const count = (await getPendingWrites()).length + (await getPendingOperations()).length;
  const effective = state || (count ? 'pending' : 'synced');
  const labels = {
    syncing: `Syncing ${count} change${count === 1 ? '' : 's'}â€¦`,
    pending: `${count} change${count === 1 ? '' : 's'} pending sync`,
    error: `Sync paused â€” ${count} change${count === 1 ? '' : 's'} safely stored`,
    synced: 'All changes synced',
  };
  el.textContent = labels[effective];
  el.dataset.state = effective;
  el.classList.toggle('visible', effective !== 'synced' || count > 0);
  if (effective === 'synced') setTimeout(() => el.classList.remove('visible'), 1800);
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
  const titles = { local: 'Saved locally â€” pending sync', saving: 'Syncingâ€¦', failed: 'Sync failed' };
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
      client_updated_at: (notes.find(n => n.id === noteId) || {}).updated_at || null,
      queued_at: Date.now(),
    });
    console.log('[sync] queued write for note', noteId);
    await updateGlobalSyncStatus('pending');
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

async function cacheImages(noteId, imageList) {
  for (const image of imageList) {
    await idbPut('cached_images', {
      ...image,
      cache_key: `${noteId}:${image.id}`,
      note_id: noteId,
      cached_at: Date.now(),
    });
  }
}

async function getCachedImages(noteId) {
  const all = await idbGetAll('cached_images');
  return all.filter(image => image.note_id === noteId && !image.locally_deleted);
}

async function replaceLocalNoteId(localId, serverNote) {
  await idbDelete('cached_notes', localId);
  await idbPut('cached_notes', { ...serverNote, cached_at: Date.now() });
  notes = notes.map(note => note.id === localId ? serverNote : note);
  if (currentNoteId === localId) currentNoteId = serverNote.id;

  const writes = await getPendingWrites();
  for (const write of writes.filter(item => item.note_id === localId)) {
    await idbDelete('pending_writes', localId);
    await idbPut('pending_writes', {
      ...write,
      note_id: serverNote.id,
      client_updated_at: serverNote.updated_at,
    });
  }
  const ops = await getPendingOperations();
  for (const op of ops.filter(item => item.note_id === localId)) {
    await idbPut('pending_ops', { ...op, note_id: serverNote.id });
  }
}

async function flushOperations() {
  const pending = (await getPendingOperations()).sort((a, b) => a.queued_at - b.queued_at);
  const noteIds = new Map();
  for (const op of pending) {
    const noteId = noteIds.get(op.note_id) || op.note_id;
    if (op.type === 'create_note') {
      const created = await apiRequest('POST', '/api/notes', op.payload);
      await replaceLocalNoteId(op.note_id, created);
      noteIds.set(op.note_id, created.id);
    } else if (op.type === 'trash_note') {
      await apiRequest('DELETE', `/api/notes/${noteId}`);
    } else if (op.type === 'upload_image') {
      const form = new FormData();
      form.append('image', op.file, op.file_name);
      const response = await fetch(`/api/notes/${noteId}/images`, {
        method: 'POST', body: form, credentials: 'same-origin', headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const uploaded = await response.json();
      await idbDelete('cached_images', `${op.note_id}:${op.local_image_id}`);
      await idbPut('cached_images', { ...uploaded, cache_key: `${noteId}:${uploaded.id}`, note_id: noteId });
    } else if (op.type === 'delete_image') {
      await apiRequest('DELETE', `/api/notes/${noteId}/images/${op.image_id}`);
    }
    await idbDelete('pending_ops', op.op_id);
  }
}

/* ===== Flush queue ===== */
async function flushQueue() {
  if (flushInProgress || !navigator.onLine) return;
  let pending = await getPendingWrites();
  const operations = await getPendingOperations();
  if (pending.length === 0 && operations.length === 0) {
    await updateGlobalSyncStatus('synced');
    return;
  }

  flushInProgress = true;
  clearTimeout(flushRetryTimer);
  await updateGlobalSyncStatus('syncing');
  console.log('[sync] flushing', pending.length, 'pending write(s)');

  // Sort by queued_at ascending
  pending.sort((a, b) => a.queued_at - b.queued_at);

  let anyFailed = false;
  try {
    await flushOperations();
    pending = await getPendingWrites();
  } catch (e) {
    console.error('[sync] operation flush failed', e);
    anyFailed = true;
  }
  for (const w of pending) {
    setSyncState(w.note_id, 'saving');
    try {
      const updated = await apiRequest('PUT', `/api/notes/${w.note_id}`, {
        title: w.title,
        body: w.body,
        body_after: w.body_after || '',
        is_pinned: w.is_pinned,
        folder_id: w.folder_id,
        client_updated_at: w.client_updated_at,
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
    await updateGlobalSyncStatus('synced');
  } else {
    await updateGlobalSyncStatus('error');
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
const btnViewConflicts = document.getElementById('btn-v×m¼îÚ$z{-®éÜj×¢¶–ÖvW5¶–G…ÒÂ–ÖvW5¶æWt–G…ÕÒÒ¶–ÖvW5¶æWt–G…ÒÂ–ÖvW5¶–G…ÕÓ°¢&VæFW$–ÖvT&Æö6·2‚“°¢6WD–ÖvU7FGW2‚t6÷VÆBæ÷B&V÷&FW"–ÖvW2âÆV6RG'’v–âârÂG'VR“°¢6öç6öÆRæW'&÷"‚t–ÖvR&V÷&FW"f–ÆVBrÂR“°¢Ð§Ð ¦7–æ2gVæ7F–öâ7&VFTföÆFW"†æÖR’°¢æÖRÒæÖRçG&–Ò‚“°¢–b‚æÖR’&WGW&ã°¢G'’°¢6öç7BföÆFW"Òv—B•&WVW7B‚uõ5BrÂrö’öföÆFW'2rÂ²æÖRÒ“°¢föÆFW'2çW6‚†föÆFW"“°¢föÆFW'2ç6÷'B‚†Â"’ÓâææÖRæÆö6ÆT6ö×&R†"ææÖR’“°¢&VæFW$föÆFW$Æ—7B‚“°¢÷VÆFTföÆFW%6VÆV7B‚“°¢Ò6F6‚†R’°¢6öç6öÆRæW'&÷"‚tf–ÆVBFò7&VFRföÆFW"rÂR“°¢Ð§Ð ¦7–æ2gVæ7F–öâFVÆWFTföÆFW"†föÆFW$–B’°¢G'’°¢v—B•&WVW7B‚tDTÄUDRrÂö’öföÆFW'2òG¶föÆFW$–GÖ“°¢föÆFW'2ÒföÆFW'2æf–ÇFW"†bÓâbæ–BÓÒföÆFW$–B“°¢òòVæf–ÆRæ÷FW2Æö6ÆÇ¢æ÷FW2æf÷$V6‚†âÓâ²–b†âæföÆFW%ö–BÓÓÒföÆFW$–B’âæföÆFW%ö–BÒçVÆÃ²Ò“°¢–b†7W'&VçDföÆFW$–BÓÓÒföÆFW$–B’7W'&VçDföÆFW$–BÒçVÆÃ°¢&VæFW$föÆFW$Æ—7B‚“°¢÷VÆFTföÆFW%6VÆV7B‚“°¢&VæFW$Æ—7B‚“°¢Ò6F6‚†R’°¢6öç6öÆRæW'&÷"‚tf–ÆVBFòFVÆWFRföÆFW"rÂR“°¢Ð§Ð ¢ò¢ÓÓÓÓÒfW'6–öâ†—7F÷'’ÓÓÓÓÒ¢ð¦7–æ2gVæ7F–öâ÷Vä†—7F÷'•æVÂ†æ÷FT–B’°¢†—7F÷'”æ÷FT–BÒæ÷FT–C°¢†—7F÷'”Æ—7Bæ–ææW$…DÔÂÒsÆF—b6Æ73Ò&†—7F÷'’ÖÆöF–ær#äÆöF–æuÇS##cÂöF—câs°¢†—7F÷'•æVÂç7G–ÆRæF—7Æ’Òrs°¢G'’°¢6öç7BfW'6–öç2Òv—B•&WVW7B‚ttUBrÂö’öæ÷FW2òG¶æ÷FT–GÒ÷fW'6–öç6“°¢–b‡fW'6–öç2æÆVæwF‚ÓÓÒ’°¢†—7F÷'”Æ—7Bæ–ææW$…DÔÂÒsÆF—b6Æ73Ò&†—7F÷'’ÖV×G’#äæòfW'6–öç26fVB–WBãÆ'#åfW'6–öç2&R7&VFVBWFöÖF–6ÆÇ’v†Vâ–÷RWFFRF†—2æ÷FRãÂöF—câs°¢&WGW&ã°¢Ð¢†—7F÷'”Æ—7Bæ–ææW$…DÔÂÒfW'6–öç2æÖ‡bÓâ°¢6öç7BBÒæWrFFR‡bç6fVEöBç&WÆ6R‚rrÂuBr’²u¢r“°¢6öç7BÆ&VÂÒBçFôÆö6ÆU7G&–ær‚vVâÔt"rÂ°¢F“¢s"ÖF–v—BrÂÖöçFƒ¢s"ÖF–v—BrÂ–V#¢vçVÖW&–2rÀ¢†÷W#¢s"ÖF–v—BrÂÖ–çWFS¢s"ÖF–v—Bp¢Ò“°¢&WGW&âÆF—b6Æ73Ò&†—7F÷'’Ö—FVÒ"FF×fW'6–öâÖ–CÒ"G·bæ–GÒ#à¢ÆF—b6Æ73Ò&†—7F÷'’Ö—FVÒÖÖWF#à¢Ç7â6Æ73Ò&†—7F÷'’Ö—FVÒÖFFR#âG¶Æ&VÇÓÂ÷7ãà¢ÂöF—cà¢ÆF—b6Æ73Ò&†—7F÷'’Ö—FVÒ×F—FÆR#âG¶W66T‡FÖÂ‡bçF—FÆRÇÂuVçF—FÆVBr—ÓÂöF—cà¢Æ'WGFöâ6Æ73Ò&'Fâ×&W7F÷&R×fW'6–öâ"FF×fW'6–öâÖ–CÒ"G·bæ–GÒ"&–ÖÆ&VÃÒ%&W7F÷&RfW'6–öâg&öÒG¶Æ&VÇÒ#å&W7F÷&SÂö'WGFöãà¢ÂöF—cæ°¢Ò’æ¦ö–â‚rr“°¢†—7F÷'”Æ—7BçVW'•6VÆV7F÷$ÆÂ‚ræ'Fâ×&W7F÷&R×fW'6–öâr’æf÷$V6‚†'FâÓâ°¢'FâæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ‚’Óâ&W7F÷&UfW'6–öâ†æ÷FT–BÂ'6T–çB†'FâæFF6WBçfW'6–öä–B’’“°¢Ò“°¢Ò6F6‚†R’°¢†—7F÷'”Æ—7Bæ–ææW$…DÔÂÒsÆF—b6Æ73Ò&†—7F÷'’ÖV×G’#äf–ÆVBFòÆöBfW'6–öâ†—7F÷'’ãÂöF—câs°¢6öç6öÆRæW'&÷"‚tf–ÆVBFòÆöB†—7F÷'’rÂR“°¢Ð§Ð ¦gVæ7F–öâ6Æ÷6T†—7F÷'•æVÂ‚’°¢†—7F÷'•æVÂç7G–ÆRæF—7Æ’ÒvæöæRs°¢†—7F÷'”æ÷FT–BÒçVÆÃ°§Ð ¦7–æ2gVæ7F–öâ&W7F÷&UfW'6–öâ†æ÷FT–BÂfW'6–öä–B’°¢–b‚6öæf—&Ò‚u&W7F÷&RF†—2fW'6–öãòF†R7W'&VçB6öçFVçBv–ÆÂ&R6fVB2æWrfW'6–öâf—'7Bâr’’&WGW&ã°¢G'’°¢6öç7BWFFVBÒv—B•&WVW7B‚uõ5BrÂö’öæ÷FW2òG¶æ÷FT–GÒ÷fW'6–öç2òG·fW'6–öä–GÒ÷&W7F÷&V“°¢6öç7B–G‚Òæ÷FW2æf–æD–æFW‚†âÓââæ–BÓÓÒæ÷FT–B“°¢–b†–G‚ÓÒÓ’æ÷FW5¶–G…ÒÒWFFVC°¢–b†7W'&VçDæ÷FT–BÓÓÒæ÷FT–B’°¢6öç7B&W&VD&öG’Ò&W&Tæ÷FT‡FÖÂ‡WFFVBæ&öG’“°¢6öç7B&W&VD&öG”gFW"Ò&W&Tæ÷FT‡FÖÂ‡WFFVBæ&öG•ögFW"ÇÂrr“°¢6öç7B&W—&VDÖ&·WÒ&W&VD&öG’ÓÒWFFVBæ&öG’ÇÀ¢&W&VD&öG”gFW"ÓÒ‡WFFVBæ&öG•ögFW"ÇÂrr“°¢WFFVBæ&öG’Ò&W&VD&öG“°¢WFFVBæ&öG•ögFW"Ò&W&VD&öG”gFW#°¢æ÷FUF—FÆRçFW‡D6öçFVçBÒWFFVBçF—FÆS°¢æ÷FT&öG’æ–ææW$…DÔÂÒ&W&VD&öG“°¢–b†æ÷FT&öG”gFW"’æ÷FT&öG”gFW"æ–ææW$…DÔÂÒ&W&VD&öG”gFW#°¢WFFTVF—F÷%FööÆ&"‡WFFVB“°¢–b‡&W—&VDÖ&·W’66†VGVÆTWF÷6fR‚“°¢Ð¢6WDWF÷6fR‚u&W7F÷&VBÇS#s2r“°¢&VæFW$Æ—7B‚“°¢6Æ÷6T†—7F÷'•æVÂ‚“°¢Ò6F6‚†R’°¢6öç6öÆRæW'&÷"‚tf–ÆVBFò&W7F÷&RfW'6–öârÂR“°¢ÆW'B‚tf–ÆVBFò&W7F÷&RfW'6–öââÆV6RG'’v–ââr“°¢Ð§Ð ¢ò¢ÓÓÓÓÒ6öæfÆ–7B&ææW"ÓÓÓÓÒ¢ð¦gVæ7F–öâ6†÷t6öæfÆ–7D&ææW"‚’°¢–b†6öæfÆ–7D&ææW"’6öæfÆ–7D&ææW"ç7G–ÆRæF—7Æ’Òrs°§Ð ¦gVæ7F–öâ†–FT6öæfÆ–7D&ææW"‚’°¢–b†6öæfÆ–7D&ææW"’6öæfÆ–7D&ææW"ç7G–ÆRæF—7Æ’ÒvæöæRs°§Ð ¦7–æ2gVæ7F–öâFVÆWFT6öæfÆ–7D6÷’‚’°¢–b‚7W'&VçDæ÷FT–B’&WGW&ã°¢6öç7Bæ÷FRÒ7W'&VçDæ÷FR‚“°¢–b‚æ÷FRÇÂæ÷FRæ6öæfÆ–7Eööb’&WGW&ã°¢6öç7B–BÒ7W'&VçDæ÷FT–C°¢G'’°¢v—B•&WVW7B‚tDTÄUDRrÂö’ö6öæfÆ–7G2òG¶–GÖ“°¢æ÷FW2Òæ÷FW2æf–ÇFW"†âÓââæ–BÓÒ–B“°¢6†÷tVF—F÷"†fÇ6R“°¢Ö–äÆ–÷WBæ6Æ74Æ—7Bç&VÖ÷fR‚vVF—F÷"Ö÷Vâr“°¢&VæFW$Æ—7B‚“°¢6WDWF÷6fR‚rr“°¢Ò6F6‚†R’°¢6öç6öÆRæW'&÷"‚tf–ÆVBFòFVÆWFR6öæfÆ–7B6÷’rÂR“°¢Ð§Ð ¢ò¢ÓÓÓÓÒWF÷6fRÓÓÓÓÒ¢ð¦gVæ7F–öâ66†VGVÆTWF÷6fR‚’°¢6WDWF÷6fR‚rr“°¢6ÆV%F–ÖV÷WB†WF÷6fUF–ÖW"“°¢WF÷6fUF–ÖW"Ò6WEF–ÖV÷WB‡6fTæ÷FRÂS“°§Ð ¢ò¢ÓÓÓÓÒf–ÇFW"ò6÷'Bò6V&6‚ÓÓÓÓÒ¢ð¦gVæ7F–öâ6WDf–ÇFW"†f–ÇFW"’°¢7W'&VçDf–ÇFW"Òf–ÇFW#°¢òò†–FRföÆFW"6V7F–öâ–âG&6‚æB6öæfÆ–7G2f–Ww0¢föÆFW%6V7F–öâç7G–ÆRæF—7Æ’Ò†f–ÇFW"ÓÓÒwG&6†VBrÇÂf–ÇFW"ÓÓÒv6öæfÆ–7G2r’òvæöæRr¢rs°¢–b†f–ÇFW"ÓÓÒwG&6†VBrÇÂf–ÇFW"ÓÓÒv6öæfÆ–7G2r’7W'&VçDföÆFW$–BÒçVÆÃ° ¢f–ÇFW%F'2æf÷$V6‚‡BÓâ°¢6öç7B—47F—fRÒBæFF6WBæf–ÇFW"ÓÓÒf–ÇFW#°¢Bæ6Æ74Æ—7BçFövvÆR‚v7F—fRrÂ—47F—fR“°¢Bç6WDGG&–'WFR‚v&–×6VÆV7FVBrÂ—47F—fRòwG'VRr¢vfÇ6Rr“°¢Ò“°¢–b†WF÷6fUF–ÖW"bb7W'&VçDæ÷FT–B’°¢6ÆV%F–ÖV÷WB†WF÷6fUF–ÖW"“°¢WF÷6fUF–ÖW"ÒçVÆÃ°¢Ð¢6†÷tVF—F÷"†fÇ6R“°¢Ö–äÆ–÷WBæ6Æ74Æ—7Bç&VÖ÷fR‚vVF—F÷"Ö÷Vâr“°¢&VæFW$föÆFW$Æ—7B‚“°¢ÆöDæ÷FW2‚“°§Ð ¦gVæ7F–öâ6WDföÆFW$f–ÇFW"†föÆFW$–B’°¢7W'&VçDföÆFW$–BÒföÆFW$–C°¢&VæFW$föÆFW$Æ—7B‚“°¢ÆöDæ÷FW2‚“°§Ð ¦gVæ7F–öâ66†VGVÆU6V&6‚‚’°¢6ÆV%F–ÖV÷WB‡6V&6…F–ÖW"“°¢6V&6…F–ÖW"Ò6WEF–ÖV÷WB‚‚’Óâ°¢6V&6…VW'’Ò6V&6„–çWBçfÇVRçG&–Ò‚“°¢ÆöDæ÷FW2‚“°¢ÒÂ4T$4…ôDT$õTä4UôÕ2“°§Ð ¢ò¢ÓÓÓÓÒWfVçG2ÓÓÓÓÒ¢ð¦'FäæWræFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ7&VFTæ÷FR“° ¦'Fä&6²æFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ‚’Óâ°¢6ÆV%F–ÖV÷WB†WF÷6fUF–ÖW"“°¢WF÷6fUF–ÖW"ÒçVÆÃ°¢6öç7Bæ÷FRÒ7W'&VçDæ÷FR‚“°¢–b†7W'&VçDæ÷FT–Bbbæ÷FRbbæ÷FRæ—5÷G&6†VB’6fTæ÷FR‚“°¢Ö–äÆ–÷WBæ6Æ74Æ—7Bç&VÖ÷fR‚vVF—F÷"Ö÷Vâr“°§Ò“° ¦'Få–âæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂFövvÆU–â“°¦'Fä&6†—fRæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂFövvÆT&6†—fR“°¦'FåG&6‚æFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂG&6„æ÷FR“°¦'Få&W7F÷&RæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ&W7F÷&Tæ÷FR“° ¦–b†'FäW‡÷'EFb’°¢'FäW‡÷'EFbæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ‚’Óâ°¢–b‚7W'&VçDæ÷FT–B’&WGW&ã°¢v–æF÷ræ÷Vâ†ö’öæ÷FW2òG¶7W'&VçDæ÷FT–GÒöW‡÷'BçFfÂuö&Ææ²r“°¢Ò“°§Ð ¦'FäFVÆWFUW&ÖæVçBæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ‚’Óâ°¢–b‚7W'&VçDæ÷FT–B’&WGW&ã°¢F–Æöt÷fW&Æ’æ6Æ74Æ—7BæFB‚wf—6–&ÆRr“°§Ò“° ¦'Fä6æ6VÄFVÆWFRæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ‚’Óâ°¢F–Æöt÷fW&Æ’æ6Æ74Æ—7Bç&VÖ÷fR‚wf—6–&ÆRr“°§Ò“° ¦'Fä6öæf—&ÔFVÆWFRæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ7–æ2‚’Óâ°¢F–Æöt÷fW&Æ’æ6Æ74Æ—7Bç&VÖ÷fR‚wf—6–&ÆRr“°¢v—BW&ÖæVçDFVÆWFR‚“°§Ò“° ¦F–Æöt÷fW&Æ’æFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂRÓâ°¢–b†RçF&vWBÓÓÒF–Æöt÷fW&Æ’’F–Æöt÷fW&Æ’æ6Æ74Æ—7Bç&VÖ÷fR‚wf—6–&ÆRr“°§Ò“° ¦Fö7VÖVçBæFDWfVçDÆ—7FVæW"‚v¶W–F÷vârÂRÓâ°¢–b†Ræ¶W’ÓÓÒtW66RrbbF–Æöt÷fW&Æ’æ6Æ74Æ—7Bæ6öçF–ç2‚wf—6–&ÆRr’’°¢F–Æöt÷fW&Æ’æ6Æ74Æ—7Bç&VÖ÷fR‚wf—6–&ÆRr“°¢Ð§Ò“° ¦æ÷FUF—FÆRæFDWfVçDÆ—7FVæW"‚v–çWBrÂ66†VGVÆTWF÷6fR“°¦æ÷FT&öG’æFDWfVçDÆ—7FVæW"‚v–çWBrÂ66†VGVÆTWF÷6fR“°¦–b†æ÷FT&öG”gFW"’æ÷FT&öG”gFW"æFDWfVçDÆ—7FVæW"‚v–çWBrÂ66†VGVÆTWF÷6fR“° ¦æ÷FUF—FÆRæFDWfVçDÆ—7FVæW"‚v¶W–F÷vârÂRÓâ°¢–b†Ræ¶W’ÓÓÒtVçFW"r’°¢Rç&WfVçDFVfVÇB‚“°¢æ÷FT&öG’æfö7W2‚“°¢Ð§Ò“° ¦f–ÇFW%F'2æf÷$V6‚‡F"Óâ°¢F"æFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ‚’Óâ6WDf–ÇFW"‡F"æFF6WBæf–ÇFW"’“°§Ò“° §6V&6„–çWBæFDWfVçDÆ—7FVæW"‚v–çWBrÂ66†VGVÆU6V&6‚“° ¢òò6ÆV"6V&6‚öâW66P§6V&6„–çWBæFDWfVçDÆ—7FVæW"‚v¶W–F÷vârÂRÓâ°¢–b†Ræ¶W’ÓÓÒtW66Rr’°¢6V&6„–çWBçfÇVRÒrs°¢6V&6…VW'’Òrs°¢ÆöDæ÷FW2‚“°¢Ð§Ò“° §6÷'E6VÆV7BæFDWfVçDÆ—7FVæW"‚v6†ævRrÂ‚’Óâ°¢7W'&VçE6÷'BÒ6÷'E6VÆV7BçfÇVS°¢ÆöDæ÷FW2‚“°§Ò“° ¦æ÷FTföÆFW%6VÆV7BæFDWfVçDÆ—7FVæW"‚v6†ævRrÂ‚’Óâ°¢6öç7B&rÒæ÷FTföÆFW%6VÆV7BçfÇVS°¢6†ævTæ÷FTföÆFW"‡&rò'6T–çB‡&r’¢çVÆÂ“°§Ò“° ¢òòæWrföÆFW"7&VF–öà¦'FäæWtföÆFW"æFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ‚’Óâ°¢æWtföÆFW$f÷&Òç7G–ÆRæF—7Æ’ÒæWtföÆFW$f÷&Òç7G–ÆRæF—7Æ’ÓÓÒvæöæRròrr¢væöæRs°¢–b†æWtföÆFW$f÷&Òç7G–ÆRæF—7Æ’ÓÒvæöæRr’°¢æWtföÆFW$–çWBçfÇVRÒrs°¢æWtföÆFW$–çWBæfö7W2‚“°¢Ð§Ò“° ¦æWtföÆFW$–çWBæFDWfVçDÆ—7FVæW"‚v¶W–F÷vârÂ7–æ2RÓâ°¢–b†Ræ¶W’ÓÓÒtVçFW"r’°¢6öç7BæÖRÒæWtföÆFW$–çWBçfÇVRçG&–Ò‚“°¢–b†æÖR’v—B7&VFTföÆFW"†æÖR“°¢æWtföÆFW$f÷&Òç7G–ÆRæF—7Æ’ÒvæöæRs°¢æWtföÆFW$–çWBçfÇVRÒrs°¢ÒVÇ6R–b†Ræ¶W’ÓÓÒtW66Rr’°¢æWtföÆFW$f÷&Òç7G–ÆRæF—7Æ’ÒvæöæRs°¢æWtföÆFW$–çWBçfÇVRÒrs°¢Ð§Ò“° ¢òòFr–çWB(	BFBFröâVçFW"÷"6öÖÖ§Ft–çWBæFDWfVçDÆ—7FVæW"‚v¶W–F÷vârÂ7–æ2RÓâ°¢–b†Ræ¶W’ÓÓÒtVçFW"rÇÂRæ¶W’ÓÓÒrÂr’°¢Rç&WfVçDFVfVÇB‚“°¢6öç7BæÖRÒFt–çWBçfÇVRç&WÆ6R‚rÂrÂrr’çG&–Ò‚“°¢–b†æÖR’v—BFEFuFôæ÷FR†æÖR“°¢Ft–çWBçfÇVRÒrs°¢ÒVÇ6R–b†Ræ¶W’ÓÓÒtW66Rr’°¢Ft–çWBçfÇVRÒrs°¢Ð§Ò“° ¢ò¢ÓÓÓÓÒ–ÖvRWÆöBWfVçG2ÓÓÓÓÒ¢ð¦'FåWÆöD–ÖvRæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ‚’Óâ–çWEWÆöD–ÖvRæ6Æ–6²‚’“°¦'Fä6ÖW&6GW&RæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ‚’Óâ–çWD6ÖW&6GW&Ræ6Æ–6²‚’“° ¦–çWEWÆöD–ÖvRæFDWfVçDÆ—7FVæW"‚v6†ævRrÂ7–æ2‚’Óâ°¢6öç7Bf–ÆRÒ–çWEWÆöD–ÖvRæf–ÆW5³Ó°¢–b†f–ÆR’v—BWÆöD–ÖvTf–ÆR†f–ÆR“°§Ò“° ¦–çWD6ÖW&6GW&RæFDWfVçDÆ—7FVæW"‚v6†ævRrÂ7–æ2‚’Óâ°¢6öç7Bf–ÆRÒ–çWD6ÖW&6GW&Ræf–ÆW5³Ó°¢–b†f–ÆR’v—BWÆöD–ÖvTf–ÆR†f–ÆR“°§Ò“° ¢ò¢ÓÓÓÓÒöffÆ–æRFWFV7F–öâÓÓÓÓÒ¢ð¦gVæ7F–öâWFFTöæÆ–æU7FGW2‚’°¢öffÆ–æT&ææW"æ6Æ74Æ—7BçFövvÆR‚wf—6–&ÆRrÂæf–vF÷"æöäÆ–æR“°¢–b†æf–vF÷"æöäÆ–æR’°¢fÇW6…VWVR‚’çF†Vâ‚‚’Óâ&VæFW$Æ—7B‚’“°¢ÒVÇ6R°¢WFFTvÆö&Å7–æ57FGW2‚“°¢Ð§Ð§v–æF÷ræFDWfVçDÆ—7FVæW"‚vöæÆ–æRrÂWFFTöæÆ–æU7FGW2“°§v–æF÷ræFDWfVçDÆ—7FVæW"‚vöffÆ–æRrÂWFFTöæÆ–æU7FGW2“°§WFFTöæÆ–æU7FGW2‚“° ¢ò¢ÓÓÓÓÒ6W'f–6Rv÷&¶W"ÓÓÓÓÒ¢ð¦–b‚w6W'f–6Uv÷&¶W"r–âæf–vF÷"’°¢v–æF÷ræFDWfVçDÆ—7FVæW"‚vÆöBrÂ‚’Óâ°¢æf–vF÷"ç6W'f–6Uv÷&¶W"ç&Vv—7FW"‚r÷7ræ§2r’æ6F6‚†6öç6öÆRæW'&÷"“°¢Ò“°§Ð ¢ò¢ÓÓÓÓÒ–æ—BÓÓÓÓÒ¢ð§6†÷tVF—F÷"†fÇ6R“°¦ÆöDföÆFW'2‚“°¦ÆöEFw2‚“°¦ÆöDæ÷FW2‚“°¦–b‡G—Vöb–æ—Dææ÷FF–öäVF—F÷"ÓÓÒvgVæ7F–öâr’–æ—Dææ÷FF–öäVF—F÷"‚“° ¢òò&W7F÷&RVWVR7FFRöâWfW'’7F'GWâ–æFW†VDD"7W'f—fW2F"ö&W7F'G2à¥&öÖ—6RæÆÂ…¶vWEVæF–æuw&—FW2‚’ÂvWEVæF–æt÷W&F–öç2‚•Ò’çF†Vâ‚…·VæF–ærÂ÷W&F–öç5Ò’Óâ°¢–b‡VæF–æræÆVæwF‚ÇÂ÷W&F–öç2æÆVæwF‚’°¢6öç6öÆRæÆör‚u·7–æ5Òf÷VæBrÂVæF–æræÆVæwF‚²÷W&F–öç2æÆVæwF‚ÂwVæF–ær6†ævR‡2’öâ7F'GWr“°¢VæF–æræf÷$V6‚‡rÓâ7–æ57FFW2ç6WB‡rææ÷FUö–BÂvÆö6Âr’“°¢WFFTvÆö&Å7–æ57FGW2†æf–vF÷"æöäÆ–æRòw7–æ6–ærr¢wVæF–ærr“°¢–b†æf–vF÷"æöäÆ–æR’fÇW6…VWVR‚’çF†Vâ‚‚’Óâ&VæFW$Æ—7B‚’“°¢ÒVÇ6R°¢WFFTvÆö&Å7–æ57FGW2‚w7–æ6VBr“°¢Ð§Ò’æ6F6‚†6öç6öÆRæW'&÷"“° ¢òòWF÷6fR–æF–6F÷"6Æ–6²(	B&WG'’f–ÆVB7–æ70¦–b†WF÷6fTVÂ’°¢WF÷6fTVÂæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ‚’Óâ°¢–b†WF÷6fTVÂæFF6WBç7–æ57FFRÓÓÒvf–ÆVBr’°¢fÇW6…&WG'”6÷VçBÒ°¢fÇW6„–å&öw&W72ÒfÇ6S°¢fÇW6…VWVR‚’çF†Vâ‚‚’Óâ&VæFW$Æ—7B‚’“°¢Ð¢Ò“°§Ð ¢ò¢ÓÓÓÓÒ†—7F÷'’æVÂWfVçG2ÓÓÓÓÒ¢ð¦–b†'Fä†—7F÷'’’°¢'Fä†—7F÷'’æFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ‚’Óâ°¢–b†7W'&VçDæ÷FT–B’÷Vä†—7F÷'•æVÂ†7W'&VçDæ÷FT–B“°¢Ò“°§Ð ¦–b†'Fä6Æ÷6T†—7F÷'’’°¢'Fä6Æ÷6T†—7F÷'’æFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ6Æ÷6T†—7F÷'•æVÂ“°§Ð ¦–b††—7F÷'•æVÂ’°¢†—7F÷'•æVÂæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂRÓâ°¢–b†RçF&vWBÓÓÒ†—7F÷'•æVÂ’6Æ÷6T†—7F÷'•æVÂ‚“°¢Ò“°§Ð ¦Fö7VÖVçBæFDWfVçDÆ—7FVæW"‚v¶W–F÷vârÂRÓâ°¢–b†Ræ¶W’ÓÓÒtW66Rrbb†—7F÷'•æVÂbb†—7F÷'•æVÂç7G–ÆRæF—7Æ’ÓÒvæöæRr’°¢6Æ÷6T†—7F÷'•æVÂ‚“°¢Ð§Ò“° ¢ò¢ÓÓÓÓÒ6öæfÆ–7B&ææW"WfVçG2ÓÓÓÓÒ¢ð¦–b†'Fåf–Wt6öæfÆ–7G2’°¢'Fåf–Wt6öæfÆ–7G2æFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ‚’Óâ°¢†–FT6öæfÆ–7D&ææW"‚“°¢6WDf–ÇFW"‚v6öæfÆ–7G2r“°¢Ò“°§Ð ¦–b†'FäF—6Ö—746öæfÆ–7D&ææW"’°¢'FäF—6Ö—746öæfÆ–7D&ææW"æFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂ†–FT6öæfÆ–7D&ææW"“°§Ð ¦–b†'FäFVÆWFT6öæfÆ–7B’°¢'FäFVÆWFT6öæfÆ–7BæFDWfVçDÆ—7FVæW"‚v6Æ–6²rÂFVÆWFT6öæfÆ–7D6÷’“°§Ð ¢ò¢ÓÓÓÓÒf÷&ÖGF–ærFööÆ&"ÓÓÓÓÒ¢ð¢òòG&6²v†–6‚VF—F&ÆR&V—27W'&VçFÇ’fö7W6VBf÷"f÷&ÖGF–æp¦ÆWBöf×EF&vWBÒçVÆÃ°¥¶æ÷FT&öG’Âæ÷FT&öG”gFW%Òæf÷$V6‚†VÂÓâ°¢–b‚VÂ’&WGW&ã°¢VÂæFDWfVçDÆ—7FVæW"‚vfö7W2rÂ‚’Óâ²öf×EF&vWBÒVÃ²Ò“°¢VÂæFDWfVçDÆ—7FVæW"‚w7FRrÂWfVçBÓâ°¢6öç7BÆ–åFW‡BÒWfVçBæ6Æ—&ö&DFF¢òWfVçBæ6Æ—&ö&DFFævWDFF‚wFW‡B÷Æ–âr¢¢rs° ¢òòv†Vâ…DÔÂ6÷W&6R—26÷–VBg&öÒÖW76vRö6öFR&Æö6²Â'&÷w6W'27FR—@¢òò2Æ—FW&ÂFW‡BâG&VB&V6övæ—6&ÆRæ÷FRÖ&·W2&–6‚FW‡B–ç7FVBà¢–b‚äõDUôÔ$µUõDuõ$RçFW7B‡Æ–åFW‡B’’&WGW&ã° ¢WfVçBç&WfVçDFVfVÇB‚“°¢öf×EF&vWBÒVÃ°¢VÂæfö7W2‚“°¢Fö7VÖVçBæW†V46öÖÖæB‚v–ç6W'D…DÔÂrÂfÇ6RÂ6æ—F—¦Tæ÷FT‡FÖÂ‡Æ–åFW‡B’“°¢66†VGVÆTWF÷6fR‚“°¢Ò“°§Ò“° ¦gVæ7F–öâöÇ”f×B†6ÖBÂfÇVR’°¢òò&W7F÷&Rfö7W2FòF†Ræ÷FR&öG’&Vf÷&RW†V7WF–ær6öÖÖæ@¢–b…öf×EF&vWB’öf×EF&vWBæfö7W2‚“°¢VÇ6Ræ÷FT&öG’æfö7W2‚“°¢Fö7VÖVçBæW†V46öÖÖæB†6ÖBÂfÇ6RÂfÇVRÇÂçVÆÂ“°¢66†VGVÆTWF÷6fR‚“°¢÷WFFTf×D7F—fU7FFR‚“°§Ð ¦gVæ7F–öâ÷WFFTf×D7F—fU7FFR‚’°¢–b†f×D'Fä&öÆB’f×D'Fä&öÆBæ6Æ74Æ—7BçFövvÆR‚v7F—fRrÂFö7VÖVçBçVW'”6öÖÖæE7FFR‚v&öÆBr’“°¢–b†f×D'Fä—FÆ–2’f×D'Fä—FÆ–2æ6Æ74Æ—7BçFövvÆR‚v7F—fRrÂFö7VÖVçBçVW'”6öÖÖæE7FFR‚v—FÆ–2r’“°¢–b†f×D'FåVæFW"’f×D'FåVæFW"æ6Æ74Æ—7BçFövvÆR‚v7F—fRrÂFö7VÖVçBçVW'”6öÖÖæE7FFR‚wVæFW&Æ–æRr’“°¢–b†f×D'Få7G&–¶R’f×D'Få7G&–¶Ræ6Æ74Æ—7BçFövvÆR‚v7F—fRrÂFö7VÖVçBçVW'”6öÖÖæE7FFR‚w7G&–¶UF‡&÷Vv‚r’“°¢–b†f×D'FåVÂ’f×D'FåVÂæ6Æ74Æ—7BçFövvÆR‚v7F—fRrÂFö7VÖVçBçVW'”6öÖÖæE7FFR‚v–ç6W'EVæ÷&FW&VDÆ—7Br’“°¢–b†f×D'FäöÂ’f×D'FäöÂæ6Æ74Æ—7BçFövvÆR‚v7F—fRrÂFö7VÖVçBçVW'”6öÖÖæE7FFR‚v–ç6W'D÷&FW&VDÆ—7Br’“°§Ð ¦Fö7VÖVçBæFDWfVçDÆ—7FVæW"‚w6VÆV7F–öæ6†ævRrÂ÷WFFTf×D7F—fU7FFR“° ¦–b†f×D'Fä&öÆB’f×D'Fä&öÆBæFDWfVçDÆ—7FVæW"‚vÖ÷W6VF÷vârÂRÓâ²Rç&WfVçDFVfVÇB‚“²öÇ”f×B‚v&öÆBr“²Ò“°¦–b†f×D'Fä—FÆ–2’f×D'Fä—FÆ–2æFDWfVçDÆ—7FVæW"‚vÖ÷W6VF÷vârÂRÓâ²Rç&WfVçDFVfVÇB‚“²öÇ”f×B‚v—FÆ–2r“²Ò“°¦–b†f×D'FåVæFW"’f×D'FåVæFW"æFDWfVçDÆ—7FVæW"‚vÖ÷W6VF÷vârÂRÓâ²Rç&WfVçDFVfVÇB‚“²öÇ”f×B‚wVæFW&Æ–æRr“²Ò“°¦–b†f×D'Få7G&–¶R’f×D'Få7G&–¶RæFDWfVçDÆ—7FVæW"‚vÖ÷W6VF÷vârÂRÓâ²Rç&WfVçDFVfVÇB‚“²öÇ”f×B‚w7G&–¶UF‡&÷Vv‚r“²Ò“°¦–b†f×D'FåVÂ’f×D'FåVÂæFDWfVçDÆ—7FVæW"‚vÖ÷W6VF÷vârÂRÓâ²Rç&WfVçDFVfVÇB‚“²öÇ”f×B‚v–ç6W'EVæ÷&FW&VDÆ—7Br“²Ò“°¦–b†f×D'FäöÂ’f×D'FäöÂæFDWfVçDÆ—7FVæW"‚vÖ÷W6VF÷vârÂRÓâ²Rç&WfVçDFVfVÇB‚“²öÇ”f×B‚v–ç6W'D÷&FW&VDÆ—7Br“²Ò“°¦–b†f×D'Fä6ÆV"’f×D'Fä6ÆV"æFDWfVçDÆ—7FVæW"‚vÖ÷W6VF÷vârÂRÓâ²Rç&WfVçDFVfVÇB‚“²öÇ”f×B‚w&VÖ÷fTf÷&ÖBr“²Ò“° ¦–b†f×D6öÆ÷"’°¢f×D6öÆ÷"æFDWfVçDÆ—7FVæW"‚v–çWBrÂ‚’ÓâöÇ”f×B‚vf÷&T6öÆ÷"rÂf×D6öÆ÷"çfÇVR’“°§Ð ¦–b†f×D†–v†Æ–v‡B’°¢f×D†–v†Æ–v‡BæFDWfVçDÆ—7FVæW"‚v–çWBrÂ‚’ÓâöÇ”f×B‚v&6´6öÆ÷"rÂf×D†–v†Æ–v‡BçfÇVR’“°§Ð ¦–b†f×E6—¦R’°¢f×E6—¦RæFDWfVçDÆ—7FVæW"‚v6†ævRrÂ‚’Óâ°¢–b‚f×E6—¦RçfÇVR’&WGW&ã°¢öÇ”f×B‚vföçE6—¦RrÂf×E6—¦RçfÇVR“°¢f×E6—¦RçfÇVRÒrs°¢Ò“°§Ð