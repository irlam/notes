/* ===================================================================
 * Annotation Editor — Milestone 5
 *
 * Data model (stored in note_images.annotation_data as JSON string):
 * {
 *   version: 1,
 *   strokes: [
 *     { tool, color, width, opacity, points: [{x,y},...] },  // pen/highlighter (normalized 0-1)
 *     { tool, color, width, opacity, x1, y1, x2, y2 },       // arrow/rectangle/circle
 *     { tool, color, width, opacity, x, y, text }            // text
 *   ]
 * }
 * Coordinates are normalized (0.0–1.0) relative to the canvas dimensions.
 * "width" is a fraction of canvas height (e.g., 0.006 ≈ 3px on a 500px canvas).
 * =================================================================== */

'use strict';

/* ---------------------------------------------------------------------------
 * State
 * ------------------------------------------------------------------------- */
const annState = {
  open: false,
  noteId: null,
  imageId: null,
  imgNaturalW: 0,
  imgNaturalH: 0,

  tool: 'pen',
  color: '#e74c3c',
  strokeWidth: 0.006,   // fraction of canvas height

  strokes: [],          // committed strokes
  currentStroke: null,  // stroke being drawn
  undoStack: [],        // snapshots of strokes[] for undo
  redoStack: [],

  // Zoom / pan (applied as CSS transform on #annotation-stage)
  zoom: 1.0,
  panX: 0,
  panY: 0,

  // Pointer tracking (touch / multi-pointer)
  activePointers: {},   // pointerId -> {x, y}
  lastPinchDist: null,
  lastPinchMid: null,

  // Text tool
  textNormX: 0,
  textNormY: 0,

  dirty: false,
  saving: false,
};

const TOOLS = ['pen', 'highlighter', 'arrow', 'rectangle', 'circle', 'text'];

/* ---------------------------------------------------------------------------
 * DOM refs (set in initAnnotationEditor)
 * ------------------------------------------------------------------------- */
let annModal, annCanvas, annCtx, annSourceImg, annStage, annWrap;
let annColorInput, annWidthInput;
let annUndoBtn, annRedoBtn, annClearBtn;
let annSaveBtn, annCancelBtn;
let annZoomInBtn, annZoomOutBtn, annZoomResetBtn;
let annStatusEl, annTextOverlay;
const annToolBtns = {};

/* ---------------------------------------------------------------------------
 * Init — call once after DOM is ready
 * ------------------------------------------------------------------------- */
function initAnnotationEditor() {
  annModal = document.getElementById('annotation-modal');
  if (!annModal) return;

  annCanvas     = document.getElementById('annotation-canvas');
  annCtx        = annCanvas.getContext('2d');
  annSourceImg  = document.getElementById('ann-source-img');
  annStage      = document.getElementById('annotation-stage');
  annWrap       = document.getElementById('annotation-canvas-wrap');
  annColorInput = document.getElementById('ann-color');
  annWidthInput = document.getElementById('ann-width');
  annUndoBtn    = document.getElementById('ann-undo');
  annRedoBtn    = document.getElementById('ann-redo');
  annClearBtn   = document.getElementById('ann-clear');
  annSaveBtn    = document.getElementById('ann-save');
  annCancelBtn  = document.getElementById('ann-cancel');
  annZoomInBtn  = document.getElementById('ann-zoom-in');
  annZoomOutBtn = document.getElementById('ann-zoom-out');
  annZoomResetBtn = document.getElementById('ann-zoom-reset');
  annStatusEl   = document.getElementById('ann-status');
  annTextOverlay = document.getElementById('ann-text-overlay');

  TOOLS.forEach(t => {
    const btn = document.getElementById(`ann-tool-${t}`);
    if (btn) {
      annToolBtns[t] = btn;
      btn.addEventListener('click', () => annSelectTool(t));
    }
  });

  annColorInput.addEventListener('input', () => { annState.color = annColorInput.value; });
  annWidthInput.addEventListener('input', () => {
    annState.strokeWidth = parseInt(annWidthInput.value, 10) * 0.002;
  });

  annUndoBtn.addEventListener('click', annUndo);
  annRedoBtn.addEventListener('click', annRedo);
  annClearBtn.addEventListener('click', annClear);
  annSaveBtn.addEventListener('click', annSave);
  annCancelBtn.addEventListener('click', annCancel);
  annZoomInBtn.addEventListener('click', () => annSetZoom(annState.zoom * 1.3));
  annZoomOutBtn.addEventListener('click', () => annSetZoom(annState.zoom / 1.3));
  annZoomResetBtn.addEventListener('click', annResetView);

  // Canvas pointer events (unified touch + mouse)
  annCanvas.addEventListener('pointerdown', onAnnPointerDown);
  annCanvas.addEventListener('pointermove', onAnnPointerMove);
  annCanvas.addEventListener('pointerup', onAnnPointerUp);
  annCanvas.addEventListener('pointercancel', onAnnPointerUp);
  annCanvas.addEventListener('contextmenu', e => e.preventDefault());

  // Wheel zoom on the wrap
  annWrap.addEventListener('wheel', onAnnWheel, { passive: false });

  // Text overlay
  annTextOverlay.addEventListener('keydown', onAnnTextKeydown);
  annTextOverlay.addEventListener('blur', commitTextStroke);

  // Global keyboard shortcuts (active only when editor is open)
  document.addEventListener('keydown', onAnnKeydown);

  // Warn on accidental browser navigation while unsaved
  window.addEventListener('beforeunload', annBeforeUnload);

  // Resize
  window.addEventListener('resize', () => { if (annState.open) annResizeCanvas(); });
}

/* ---------------------------------------------------------------------------
 * Open / Close
 * ------------------------------------------------------------------------- */
function openAnnotationEditor(noteId, imageId, imgUrl, annotationData) {
  annState.noteId = noteId;
  annState.imageId = imageId;
  annState.strokes = [];
  annState.undoStack = [];
  annState.redoStack = [];
  annState.currentStroke = null;
  annState.zoom = 1;
  annState.panX = 0;
  annState.panY = 0;
  annState.dirty = false;
  annState.saving = false;
  annState.open = true;
  annState.activePointers = {};

  if (annotationData) {
    try {
      const d = typeof annotationData === 'string'
        ? JSON.parse(annotationData)
        : annotationData;
      annState.strokes = d.strokes || [];
    } catch (e) {
      annState.strokes = [];
    }
  }

  annModal.style.display = '';
  document.body.style.overflow = 'hidden';
  if (annStatusEl) annStatusEl.textContent = '';
  annSelectTool('pen');
  annUpdateUndoRedo();

  annSourceImg.onload = () => {
    annState.imgNaturalW = annSourceImg.naturalWidth || annSourceImg.width;
    annState.imgNaturalH = annSourceImg.naturalHeight || annSourceImg.height;
    annResizeCanvas();
    annRedrawAll();
  };
  annSourceImg.src = imgUrl;
  if (annSourceImg.complete && annSourceImg.naturalWidth) {
    annSourceImg.onload();
  }
}

function annCloseEditor() {
  annState.open = false;
  annModal.style.display = 'none';
  document.body.style.overflow = '';
  if (annTextOverlay) {
    annTextOverlay.style.display = 'none';
    annTextOverlay.value = '';
  }
}

function annCancel() {
  if (annState.dirty && !confirm('Discard unsaved annotation changes?')) return;
  annCloseEditor();
}

function annBeforeUnload(e) {
  if (annState.open && annState.dirty) {
    e.preventDefault();
    e.returnValue = 'You have unsaved annotation changes.';
  }
}

/* ---------------------------------------------------------------------------
 * Canvas sizing & transform
 * ------------------------------------------------------------------------- */
function annResizeCanvas() {
  const wW = annWrap.clientWidth || 1;
  const wH = annWrap.clientHeight || 1;
  const imgW = annState.imgNaturalW || 1;
  const imgH = annState.imgNaturalH || 1;

  // Fit image within the wrap, never up-scale beyond natural size
  const scale = Math.min(wW / imgW, wH / imgH, 1);
  const dispW = Math.max(1, Math.round(imgW * scale));
  const dispH = Math.max(1, Math.round(imgH * scale));

  annSourceImg.style.width  = dispW + 'px';
  annSourceImg.style.height = dispH + 'px';
  annCanvas.width  = dispW;
  annCanvas.height = dispH;
  annCanvas.style.width  = dispW + 'px';
  annCanvas.style.height = dispH + 'px';

  annApplyTransform();
}

function annApplyTransform() {
  annStage.style.transform =
    `translate(${annState.panX}px,${annState.panY}px) scale(${annState.zoom})`;
}

function annSetZoom(z) {
  annState.zoom = Math.max(0.25, Math.min(8, z));
  annApplyTransform();
}

function annResetView() {
  annState.zoom = 1;
  annState.panX = 0;
  annState.panY = 0;
  annApplyTransform();
}

/* ---------------------------------------------------------------------------
 * Tool selection
 * ------------------------------------------------------------------------- */
function annSelectTool(tool) {
  annState.tool = tool;
  TOOLS.forEach(t => {
    if (annToolBtns[t]) annToolBtns[t].classList.toggle('active', t === tool);
  });
  annCanvas.style.cursor = tool === 'text' ? 'text' : 'crosshair';
  if (tool !== 'text' && annTextOverlay) {
    annTextOverlay.style.display = 'none';
    annTextOverlay.value = '';
  }
}

/* ---------------------------------------------------------------------------
 * Coordinate helpers
 * The canvas is CSS-transformed (zoom/pan). getBoundingClientRect() returns
 * the visual size/position, so we can back-calculate canvas pixel coordinates.
 * ------------------------------------------------------------------------- */
function annGetCanvasCoords(clientX, clientY) {
  const rect = annCanvas.getBoundingClientRect();
  const scaleX = annCanvas.width  / rect.width;
  const scaleY = annCanvas.height / rect.height;
  return {
    x: (clientX - rect.left) * scaleX,
    y: (clientY - rect.top)  * scaleY,
  };
}

function annNorm(cx, cy) {
  return { x: cx / annCanvas.width, y: cy / annCanvas.height };
}

/* ---------------------------------------------------------------------------
 * Pointer event handlers
 * ------------------------------------------------------------------------- */
function onAnnPointerDown(e) {
  e.preventDefault();
  annState.activePointers[e.pointerId] = { x: e.clientX, y: e.clientY };
  const count = Object.keys(annState.activePointers).length;

  if (count >= 2) {
    // Two fingers: cancel current stroke, enter pan/zoom mode
    annState.currentStroke = null;
    const pts = Object.values(annState.activePointers);
    annState.lastPinchDist = _ptDist(pts[0], pts[1]);
    annState.lastPinchMid  = _ptMid(pts[0], pts[1]);
    return;
  }

  if (annState.tool === 'text') {
    const cc = annGetCanvasCoords(e.clientX, e.clientY);
    const norm = annNorm(cc.x, cc.y);
    annState.textNormX = norm.x;
    annState.textNormY = norm.y;
    annTextOverlay.value = '';
    annTextOverlay.style.display = 'block';
    // Position overlay near the tap using the canvas bounding rect
    const rect = annCanvas.getBoundingClientRect();
    const vx = e.clientX - rect.left;
    const vy = e.clientY - rect.top;
    annTextOverlay.style.left = (rect.left + vx) + 'px';
    annTextOverlay.style.top  = (rect.top  + vy) + 'px';
    annTextOverlay.focus();
    return;
  }

  annCanvas.setPointerCapture(e.pointerId);
  const cc   = annGetCanvasCoords(e.clientX, e.clientY);
  const norm = annNorm(cc.x, cc.y);

  annState.currentStroke = {
    tool:    annState.tool,
    color:   annState.color,
    width:   annState.strokeWidth,
    opacity: annState.tool === 'highlighter' ? 0.4 : 1.0,
    points:  [norm],
    x1: norm.x, y1: norm.y,
    x2: norm.x, y2: norm.y,
  };
}

function onAnnPointerMove(e) {
  e.preventDefault();
  annState.activePointers[e.pointerId] = { x: e.clientX, y: e.clientY };
  const count = Object.keys(annState.activePointers).length;

  if (count >= 2) {
    const pts = Object.values(annState.activePointers);
    const newDist = _ptDist(pts[0], pts[1]);
    const newMid  = _ptMid(pts[0], pts[1]);

    if (annState.lastPinchDist) {
      // Pinch zoom
      const factor = newDist / annState.lastPinchDist;
      annSetZoom(annState.zoom * factor);

      // Pan by midpoint delta
      if (annState.lastPinchMid) {
        annState.panX += newMid.x - annState.lastPinchMid.x;
        annState.panY += newMid.y - annState.lastPinchMid.y;
        annApplyTransform();
      }
    }
    annState.lastPinchDist = newDist;
    annState.lastPinchMid  = newMid;
    return;
  }

  if (!annState.currentStroke) return;
  const cc   = annGetCanvasCoords(e.clientX, e.clientY);
  const norm = annNorm(cc.x, cc.y);
  const s    = annState.currentStroke;

  if (s.tool === 'pen' || s.tool === 'highlighter') {
    s.points.push(norm);
  } else {
    s.x2 = norm.x;
    s.y2 = norm.y;
  }
  annRedrawAll();
  annDrawStroke(annCtx, s, annCanvas.width, annCanvas.height);
}

function onAnnPointerUp(e) {
  delete annState.activePointers[e.pointerId];
  annState.lastPinchDist = null;
  annState.lastPinchMid  = null;

  if (annState.currentStroke) {
    annPushUndo();
    annState.strokes.push(annState.currentStroke);
    annState.currentStroke = null;
    annState.dirty = true;
    annRedrawAll();
    annUpdateUndoRedo();
  }
}

function onAnnWheel(e) {
  e.preventDefault();
  const factor = e.deltaY > 0 ? 0.9 : 1.1;
  annSetZoom(annState.zoom * factor);
}

/* ---------------------------------------------------------------------------
 * Drawing
 * ------------------------------------------------------------------------- */
function annRedrawAll() {
  annCtx.clearRect(0, 0, annCanvas.width, annCanvas.height);
  const W = annCanvas.width, H = annCanvas.height;
  annState.strokes.forEach(s => annDrawStroke(annCtx, s, W, H));
}

function annDrawStroke(ctx, stroke, W, H) {
  ctx.save();
  ctx.globalAlpha   = stroke.opacity;
  ctx.strokeStyle   = stroke.color;
  ctx.fillStyle     = stroke.color;
  ctx.lineWidth     = Math.max(1, stroke.width * H);
  ctx.lineCap       = 'round';
  ctx.lineJoin      = 'round';

  switch (stroke.tool) {
    case 'pen':
    case 'highlighter':
      _drawFreehand(ctx, stroke.points, W, H);
      break;
    case 'arrow':
      _drawArrow(ctx, stroke.x1 * W, stroke.y1 * H, stroke.x2 * W, stroke.y2 * H);
      break;
    case 'rectangle':
      _drawRect(ctx, stroke.x1 * W, stroke.y1 * H, stroke.x2 * W, stroke.y2 * H);
      break;
    case 'circle':
      _drawEllipse(ctx, stroke.x1 * W, stroke.y1 * H, stroke.x2 * W, stroke.y2 * H);
      break;
    case 'text':
      _drawText(ctx, stroke, W, H);
      break;
    default:
      break;
  }
  ctx.restore();
}

function _drawFreehand(ctx, points, W, H) {
  if (!points || points.length === 0) return;
  if (points.length === 1) {
    ctx.beginPath();
    ctx.arc(points[0].x * W, points[0].y * H, ctx.lineWidth / 2, 0, Math.PI * 2);
    ctx.fill();
    return;
  }
  ctx.beginPath();
  ctx.moveTo(points[0].x * W, points[0].y * H);
  for (let i = 1; i < points.length - 1; i++) {
    const mx = ((points[i].x + points[i + 1].x) / 2) * W;
    const my = ((points[i].y + points[i + 1].y) / 2) * H;
    ctx.quadraticCurveTo(points[i].x * W, points[i].y * H, mx, my);
  }
  ctx.lineTo(points[points.length - 1].x * W, points[points.length - 1].y * H);
  ctx.stroke();
}

function _drawArrow(ctx, x1, y1, x2, y2) {
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();

  const angle   = Math.atan2(y2 - y1, x2 - x1);
  const headLen = Math.max(ctx.lineWidth * 4, 10);
  const spread  = Math.PI / 6;
  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - headLen * Math.cos(angle - spread),
             y2 - headLen * Math.sin(angle - spread));
  ctx.lineTo(x2 - headLen * Math.cos(angle + spread),
             y2 - headLen * Math.sin(angle + spread));
  ctx.closePath();
  ctx.fill();
}

function _drawRect(ctx, x1, y1, x2, y2) {
  ctx.beginPath();
  ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
}

function _drawEllipse(ctx, x1, y1, x2, y2) {
  const cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
  const rx = Math.abs(x2 - x1) / 2, ry = Math.abs(y2 - y1) / 2;
  if (rx < 1 || ry < 1) return;
  ctx.beginPath();
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  ctx.stroke();
}

function _drawText(ctx, stroke, W, H) {
  // font size stored as a fraction of canvas height (like strokeWidth)
  const fontSize = Math.max(10, Math.round(stroke.width * H * 8));
  ctx.font = `${fontSize}px sans-serif`;
  ctx.fillText(stroke.text || '', stroke.x * W, stroke.y * H);
}

/* ---------------------------------------------------------------------------
 * Text tool
 * ------------------------------------------------------------------------- */
function onAnnTextKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    commitTextStroke();
  } else if (e.key === 'Escape') {
    annTextOverlay.style.display = 'none';
    annTextOverlay.value = '';
  }
}

function commitTextStroke() {
  const text = (annTextOverlay.value || '').trim();
  annTextOverlay.style.display = 'none';
  annTextOverlay.value = '';
  if (!text) return;
  annPushUndo();
  annState.strokes.push({
    tool:    'text',
    color:   annState.color,
    width:   annState.strokeWidth,
    opacity: 1.0,
    x:       annState.textNormX,
    y:       annState.textNormY,
    text,
  });
  annState.dirty = true;
  annRedrawAll();
  annUpdateUndoRedo();
}

/* ---------------------------------------------------------------------------
 * Undo / Redo
 * ------------------------------------------------------------------------- */
const _ANN_MAX_UNDO = 50;

function annPushUndo() {
  annState.undoStack.push(JSON.parse(JSON.stringify(annState.strokes)));
  if (annState.undoStack.length > _ANN_MAX_UNDO) {
    annState.undoStack.shift();
  }
  annState.redoStack = [];
}

function annUndo() {
  if (!annState.undoStack.length) return;
  annState.redoStack.push(JSON.parse(JSON.stringify(annState.strokes)));
  annState.strokes = annState.undoStack.pop();
  annState.dirty = true;
  annRedrawAll();
  annUpdateUndoRedo();
}

function annRedo() {
  if (!annState.redoStack.length) return;
  annState.undoStack.push(JSON.parse(JSON.stringify(annState.strokes)));
  annState.strokes = annState.redoStack.pop();
  annState.dirty = true;
  annRedrawAll();
  annUpdateUndoRedo();
}

function annClear() {
  if (!annState.strokes.length) return;
  if (!confirm('Clear all annotations?')) return;
  annPushUndo();
  annState.strokes = [];
  annState.dirty = true;
  annRedrawAll();
  annUpdateUndoRedo();
}

function annUpdateUndoRedo() {
  if (annUndoBtn) annUndoBtn.disabled = annState.undoStack.length === 0;
  if (annRedoBtn) annRedoBtn.disabled = annState.redoStack.length === 0;
}

/* ---------------------------------------------------------------------------
 * Save
 * ------------------------------------------------------------------------- */
async function annSave() {
  if (annState.saving) return;
  annState.saving = true;
  annSaveBtn.disabled = true;
  if (annStatusEl) annStatusEl.textContent = 'Saving…';

  const payload = {
    annotation_data: JSON.stringify({ version: 1, strokes: annState.strokes }),
  };

  try {
    const res = await fetch(
      `/api/notes/${annState.noteId}/images/${annState.imageId}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const updated = await res.json();

    // Update the shared images array (defined in app.js)
    if (typeof images !== 'undefined') {
      const idx = images.findIndex(i => i.id === annState.imageId);
      if (idx !== -1) images[idx] = updated;
    }

    annState.dirty = false;
    if (annStatusEl) {
      annStatusEl.textContent = 'Saved ✓';
      setTimeout(() => { if (annStatusEl) annStatusEl.textContent = ''; }, 2000);
    }

    // Re-render image blocks to update preview
    if (typeof renderImageBlocks === 'function') renderImageBlocks();
  } catch (err) {
    if (annStatusEl) annStatusEl.textContent = 'Save failed';
    console.error('Annotation save failed', err);
  } finally {
    annState.saving = false;
    if (annSaveBtn) annSaveBtn.disabled = false;
  }
}

/* ---------------------------------------------------------------------------
 * Keyboard shortcuts (only active when editor is open)
 * ------------------------------------------------------------------------- */
function onAnnKeydown(e) {
  if (!annState.open) return;
  if (document.activeElement === annTextOverlay) return;

  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'z') {
    e.preventDefault(); annUndo();
  } else if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'y' || (e.shiftKey && e.key.toLowerCase() === 'z'))) {
    e.preventDefault(); annRedo();
  } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault(); annSave();
  } else if (e.key === 'Escape') {
    annCancel();
  } else if (!e.ctrlKey && !e.metaKey) {
    const map = { p: 'pen', h: 'highlighter', a: 'arrow', r: 'rectangle', c: 'circle', t: 'text' };
    if (map[e.key.toLowerCase()]) annSelectTool(map[e.key.toLowerCase()]);
  }
}

/* ---------------------------------------------------------------------------
 * Preview rendering (used in note view to composite annotations onto image)
 * Called from app.js renderImageBlocks()
 * ------------------------------------------------------------------------- */
function renderAnnotationPreview(canvas, imgEl, annotationData) {
  const ctx = canvas.getContext('2d');
  canvas.width  = imgEl.naturalWidth  || imgEl.width  || canvas.offsetWidth  || 1;
  canvas.height = imgEl.naturalHeight || imgEl.height || canvas.offsetHeight || 1;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(imgEl, 0, 0, canvas.width, canvas.height);

  if (!annotationData) return;

  let data;
  try {
    data = typeof annotationData === 'string' ? JSON.parse(annotationData) : annotationData;
  } catch (e) { return; }

  const W = canvas.width, H = canvas.height;
  (data.strokes || []).forEach(s => annDrawStroke(ctx, s, W, H));
}

/* ---------------------------------------------------------------------------
 * Utility helpers
 * ------------------------------------------------------------------------- */
function _ptDist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function _ptMid(a, b) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

/* ---------------------------------------------------------------------------
 * Expose public API
 * ------------------------------------------------------------------------- */
window.openAnnotationEditor    = openAnnotationEditor;
window.renderAnnotationPreview = renderAnnotationPreview;
window.initAnnotationEditor    = initAnnotationEditor;
