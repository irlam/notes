# Milestone 5 — Image Annotation Editor

## Annotation Data Model

Annotation data is stored as a JSON string in the `note_images.annotation_data` column
(added in Migration 004).  No schema migration is needed for Milestone 5.

### Top-level structure

```json
{
  "version": 1,
  "strokes": [ … ]
}
```

### Stroke object fields

| Field | Type | Present for | Description |
|-------|------|-------------|-------------|
| `tool` | string | all | `"pen"`, `"highlighter"`, `"arrow"`, `"rectangle"`, `"circle"`, `"text"` |
| `color` | string | all | CSS hex colour, e.g. `"#e74c3c"` |
| `width` | number | all | Normalised stroke width = `lineWidth / canvasHeight` (pen/highlighter/shapes); for text: `fontSize = width * canvasHeight * 8` |
| `opacity` | number | all | 0.0–1.0; highlighter defaults to 0.4 |
| `points` | array | pen, highlighter | `[{"x": 0.1, "y": 0.2}, …]` — normalised coordinates 0.0–1.0 |
| `x1`, `y1`, `x2`, `y2` | number | arrow, rectangle, circle | Normalised bounding box |
| `x`, `y` | number | text | Normalised text baseline origin |
| `text` | string | text | The label text |

All coordinates are **normalised (0.0–1.0)** relative to the canvas dimensions so
annotations scale correctly when previewed at any resolution.

---

## Tool Behaviours

| Tool | Shortcut | Behaviour |
|------|----------|-----------|
| **Pen** | `P` | Freehand smooth line using quadratic Bézier fitting |
| **Highlighter** | `H` | Same as pen but 40% opacity and wider default |
| **Arrow** | `A` | Line from drag-start to drag-end, with filled arrowhead |
| **Rectangle** | `R` | Hollow rectangle (drag to define bounding box) |
| **Circle** | `C` | Hollow ellipse (drag to define bounding box) |
| **Text** | `T` | Tap/click to position; type in floating overlay; Enter to place |

**Colour picker**: any CSS colour via `<input type="color">`.

**Width slider**: range 1–20.  Maps to `strokeWidth = sliderValue × 0.002`.
For the text tool the same slider controls font size (`fontSize = width × H × 8`).

**Undo / Redo**: full history; keyboard shortcuts `Ctrl+Z` / `Ctrl+Y` (or `Ctrl+Shift+Z`).

**Clear all**: confirmation prompt before discarding all strokes.

---

## Storage & Rendering Choices

### Original image — preserved unchanged
The server stores only the compressed original file on disk.  Annotations are
**never baked into the image file**.

### Annotation data — stored as JSON in SQLite
`PUT /api/notes/<note_id>/images/<image_id>` accepts `{ "annotation_data": "…" }`
(a JSON string or object) and persists it in the `annotation_data` TEXT column.
Clearing annotations is done by passing `null`.

### Preview in note view — client-side canvas composite
When a note is opened, `renderImageBlocks()` checks each image's `annotation_data`.
If present, a `<canvas>` element is rendered instead of a plain `<img>`:

1. The original image is drawn with `ctx.drawImage()`.
2. `renderAnnotationPreview()` iterates the stored strokes and redraws them at
   the display resolution using normalised coordinates.

This approach requires **no server-side graphics library** (e.g. Pillow, ImageMagick).
It works on standard Plesk PHP/Python shared hosting where privileged graphics
daemons are unavailable.

### Annotation editor — Canvas 2D API
The editor mounts a `<canvas>` element directly on top of the `<img>` inside a
CSS-transformed `#annotation-stage`.  Drawing uses the `PointerEvent` API
(unified mouse + touch + stylus support).

---

## Manual QA Checklist

### Setup
- [ ] Log in and open a note with at least one uploaded image.

### Opening the editor
- [ ] Click the ✏️ button on an image block → annotation modal opens full-screen.
- [ ] Image is displayed centred in the canvas area.
- [ ] For a previously annotated image, existing annotations are visible.

### Drawing tools
- [ ] **Pen** — drag/swipe draws a smooth freehand stroke.
- [ ] **Highlighter** — drag/swipe draws a semi-transparent wide stroke.
- [ ] **Arrow** — drag from A to B creates a line with arrowhead at B.
- [ ] **Rectangle** — drag draws a hollow rectangle.
- [ ] **Circle** — drag draws a hollow ellipse.
- [ ] **Text** — tap canvas, type in floating input, press Enter → text placed on canvas.
- [ ] Colour picker changes stroke colour immediately.
- [ ] Width slider changes stroke thickness immediately.
- [ ] Keyboard shortcuts `P H A R C T` switch tools.

### Undo / Redo
- [ ] Undo (`Ctrl+Z`) removes the last stroke.
- [ ] Redo (`Ctrl+Y`) reapplies it.
- [ ] Undo button disabled when nothing to undo; Redo disabled when nothing to redo.
- [ ] Clear all → confirmation prompt → all strokes removed.

### Zoom / Pan
- [ ] Scroll wheel zooms in/out.
- [ ] `＋` / `－` buttons zoom in/out.
- [ ] `⊡` button resets zoom and pan.
- [ ] On tablet: two-finger pinch zooms; two-finger drag pans.
- [ ] Drawing tools work correctly after zoom/pan (coordinates stay aligned).

### Touch interactions (tablet / phone)
- [ ] Single-finger draw works for all tools.
- [ ] Two-finger pinch zooms without creating stray strokes.
- [ ] Two-finger drag pans without creating stray strokes.
- [ ] Text tool floating input accepts keyboard input on mobile.

### Save / Reopen
- [ ] Click **Save** → "Saving…" → "Saved ✓".
- [ ] Close and reopen the note → image shows annotated preview.
- [ ] Click ✏️ again → editor opens with saved annotations intact.
- [ ] Original image is unchanged (verify via `/media/<filename>`).

### Accidental navigation guard
- [ ] Draw something (unsaved) → click ✕ Cancel → confirm dialog appears.
- [ ] Accept discard → editor closes without saving.
- [ ] Draw something → attempt to close browser tab → browser warns about unsaved changes.

### Clear annotations
- [ ] Save with null annotations → image preview returns to plain `<img>` (no canvas).

### User isolation
- [ ] Log in as a second user → cannot access or modify another user's image annotations.

---

## Known Limitations & Performance Notes

- **Large freehand strokes**: Each pointer-move event appends a new point.  A long,
  detailed freehand stroke can accumulate hundreds of points.  Redraw on each move
  re-draws the entire canvas; on slow devices this may lag slightly.  Mitigation:
  quadratic Bézier smoothing reduces the visual impact of point thinning.

- **Undo history memory**: Each undo entry deep-copies the entire strokes array.
  If users draw many complex strokes the undo stack can consume noticeable memory.
  No current cap is enforced.

- **Canvas size capped at natural image dimensions**: The canvas is never
  up-scaled beyond the original image resolution, so annotations are stored at
  the original image's pixel resolution.  Very large images (close to the 1920 px
  upload cap) produce a proportionally large canvas and may redraw slowly.

- **Text tool keyboard on mobile**: iOS/Android virtual keyboards shift the
  viewport when a text `<textarea>` receives focus.  The floating text overlay
  may appear off-screen on small devices.  Users can scroll to find it.

- **GIF animations**: The original image is displayed as a static first frame in
  the canvas preview; the animation is not replayed in the annotation editor or
  composite preview.

- **No server-side composite image**: The annotated preview is generated
  client-side only.  If a future requirement needs a shareable PNG with
  annotations baked in, a separate export feature using `canvas.toBlob()` would
  be straightforward to add.

- **Plesk compatibility**: All annotation logic is pure client-side JavaScript
  with the Canvas 2D API.  No additional Python packages or server daemons are
  required.
