# UI Screens — Notes PWA

> Screen inventory and wireframe notes for notes.defecttracker.uk.  
> All screens must be functional when installed as a PWA (standalone display mode).

---

## Screen List

| ID | Screen | Route | Status |
|---|---|---|---|
| S-01 | Main / Note Editor | `/` | ✅ Implemented |
| S-02 | Offline Banner (overlay) | n/a — inline state | ✅ Implemented |
| S-03 | Delete Confirmation (dialog) | n/a — modal | ✅ Implemented |
| S-04 | Sync Status Chip | n/a — inline state | 🔲 Planned (M2) |
| S-05 | Image Annotation Editor | n/a — modal/panel | 🔲 Planned (M3) |
| S-06 | PDF Export Preview | n/a — print dialog / modal | 🔲 Planned (M3) |
| S-07 | Search / Filter Bar | n/a — inline (list pane) | 🔲 Planned (M4) |
| S-08 | Tag Management | n/a — inline / sidebar | 🔲 Planned (M4) |
| S-09 | Login | `/login` | 🔲 Planned (M5+) |
| S-10 | Register | `/register` | 🔲 Planned (M5+) |

---

## S-01 — Main / Note Editor

### Layout (two-pane, desktop ≥ 768 px wide)

```
┌──────────────────────────────────────────────────────────────┐
│  [App title / logo]                    [Install PWA button]  │
├────────────────────┬─────────────────────────────────────────┤
│  [+ New Note]      │  [Note title input]        [Sync chip]  │
│  ─────────────     │  ─────────────────────────────────────  │
│  Note A (active) ● │                                         │
│  Note B            │  [Note body textarea / rich-text area]  │
│  Note C            │                                         │
│  Note D            │                                         │
│  …                 │                                         │
│                    │                           [Delete btn]  │
└────────────────────┴─────────────────────────────────────────┘
```

### Layout (mobile, < 768 px)

- List pane is shown first; tapping a note slides to the editor pane.
- A back button returns to the list pane.
- Bottom navigation bar or swipe gesture for pane switching.

### Key Elements

| Element | Notes |
|---|---|
| Note list | Sorted by `updated_at` desc; shows title + truncated first line + relative timestamp |
| `+ New Note` button | Min 44 × 44 px tap target; always visible at top of list |
| Title input | Auto-focused when a note is selected; placeholder "Untitled" |
| Body area | Full-height, scrollable; autosave triggered on change |
| Sync chip | Top-right of editor; states: Saved ✓ / Saving… / Unsaved / Error ✗ (M2) |
| Delete button | In editor footer; opens S-03 confirmation dialog |
| Offline banner | S-02; appears below the header when `navigator.onLine === false` |

---

## S-02 — Offline Banner

- **Trigger:** `window` `offline` event.
- **Dismissal:** Automatically hidden on `online` event.
- **Text:** "You are offline. Changes will sync when you reconnect."
- **Position:** Sticky banner below the top navigation bar.
- **Colour:** Amber/yellow background, dark text; high contrast.

---

## S-03 — Delete Confirmation Dialog

- **Trigger:** User clicks/taps Delete button in the editor.
- **Content:** "Delete this note? This cannot be undone."
- **Actions:** Cancel (secondary) | Delete (destructive / red).
- **Keyboard:** Esc → Cancel; Enter → no default action (avoid accidental delete).
- **Accessibility:** Dialog role `alertdialog`; focus trapped inside modal.

---

## S-04 — Sync Status Chip (Milestone 2)

States and visual treatment:

| State | Label | Icon | Colour |
|---|---|---|---|
| Saved | Saved ✓ | Checkmark | Green |
| Saving | Saving… | Spinner | Blue |
| Unsaved | Unsaved changes | Dot | Amber |
| Error | Error — tap to retry | Cross | Red |

- Chip positioned top-right of editor pane.
- Transitions between states are animated (fade / cross-fade, ≤ 200 ms).
- Error state shows a tap/click target to trigger manual retry.

---

## S-05 — Image Annotation Editor (Milestone 3)

- Opens as a modal (or full-screen overlay on mobile) when user clicks an inline image.
- Canvas layer drawn on top of the image.
- Toolbar: pen, eraser, colour picker, undo, save annotation, close.
- Save persists the annotation as SVG overlay or merged PNG (decision OD-5 required).
- Annotated images display a small "annotated" badge in the note body view.

---

## S-06 — PDF Export (Milestone 3)

- Triggered by "Export PDF" button in the editor toolbar.
- On desktop: opens browser print dialog with `@media print` styles applied.
- PDF includes: note title, body (rich text rendered), inline images with annotations.
- Optional: server-side PDF generation endpoint for more reliable cross-browser output (decision OD-4 required).

---

## S-07 — Search / Filter Bar (Milestone 4)

- Located at the top of the note list pane.
- Real-time client-side filter as the user types.
- Clears with an × button.
- Highlights matching text in the note titles/snippets.

---

## S-08 — Tag Management (Milestone 4)

- Tags shown as chips below the note title in the list pane.
- Tag editor inline in the note editor (autocomplete + create new).
- Tag filter: clicking a tag in the list pane filters to notes with that tag.

---

## S-09 — Login (Milestone 5+)

*Placeholder — not yet designed.*

---

## S-10 — Register (Milestone 5+)

*Placeholder — not yet designed.*

---

## Design Tokens (to be defined)

| Token | Value (proposed) |
|---|---|
| Primary colour | `#1a73e8` (blue) |
| Destructive colour | `#d93025` (red) |
| Warning / offline colour | `#f9ab00` (amber) |
| Success / saved colour | `#1e8e3e` (green) |
| Font | System UI stack (`-apple-system`, `Segoe UI`, `Roboto`, sans-serif) |
| Border radius | `8px` |
| Min touch target | `44px × 44px` |

---

## Open Questions (UI)

| # | Question |
|---|---|
| UI-1 | Should mobile use a bottom tab bar or a slide-over pane for navigation? |
| UI-2 | Should the note list show a preview of the first image in the note? |
| UI-3 | Should the sync chip always be visible, or only when the state is non-saved? |
