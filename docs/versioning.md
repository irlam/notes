# Milestone 9 — Version History & Conflict Copy Management

## 1. Versioning Model Summary

### Overview

Every time a note is saved (via `PUT /api/notes/<id>`), the server automatically
takes a **snapshot** of the previous title and body before overwriting.  Snapshots
are stored in the `note_versions` table and are never shown in the main note list.

### Data model

```
note_versions
  id         INTEGER PRIMARY KEY
  note_id    INTEGER NOT NULL  → notes.id ON DELETE CASCADE
  user_id    INTEGER NOT NULL  → users.id
  title      TEXT NOT NULL DEFAULT ''
  body       TEXT NOT NULL DEFAULT ''
  saved_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
```

The `conflict_of` column added to `notes` (migration 005) identifies conflict
copies:

```
notes.conflict_of  INTEGER  -- NULL = normal note; non-NULL = conflict copy of that note id
```

### API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/notes/<id>/versions` | List snapshots for a note (newest first) |
| `POST` | `/api/notes/<id>/versions/<vid>/restore` | Restore note to a previous snapshot |
| `GET`  | `/api/conflicts` | List all conflict copies for the current user |
| `DELETE` | `/api/conflicts/<id>` | Permanently delete a conflict copy |

### Snapshot lifecycle

1. User edits a note → autosave fires (`PUT /api/notes/<id>`).
2. **Before** overwriting, the server calls `_snapshot()` to insert a row into
   `note_versions` containing the existing title and body.
3. The note record is updated with the new content.
4. `_prune_versions()` is called to enforce the 50-version cap (see §3).

### Restore flow

1. User opens the Version History panel (🕐 button in toolbar).
2. User clicks **Restore** on any listed version.
3. A `POST /api/notes/<id>/versions/<vid>/restore` request is sent.
4. The server **first snapshots the current content** so the restore itself is
   undoable, then applies the historical version.
5. The editor is updated in place; the history panel closes.

---

## 2. Conflict UX Summary

### When a conflict copy is created

A conflict copy is created when:
- The client sends a `PUT /api/notes/<id>` request **and** includes a
  `client_updated_at` field whose value **differs** from the server's current
  `notes.updated_at` timestamp.

This can happen when:
- The note was edited in another browser tab or device since the client last
  fetched it.
- An offline write was flushed after the server note had already moved on.

### What happens

1. The server creates a new note row with:
   - `title` = `[Conflict Copy] <original title>` (truncated to 500 chars)
   - `body` = the **server's current body** (the version the client did not have)
   - `conflict_of` = the original note's `id`
2. The server then applies the **client's** new title and body to the original note.
3. The `PUT` response includes a `conflict_note_id` field with the new conflict
   copy's `id`.

### User-facing experience

- A **conflict banner** (`⚠️ A conflict copy was created.`) appears at the bottom
  of the screen immediately after a conflicting save.
- The banner offers **View Conflicts** (switches to the Conflicts filter tab) and
  a dismiss button.
- The **⚠ Conflicts** tab in the sidebar shows all conflict copies, each labelled
  `[Conflict Copy] …` and marked with a ⚠ prefix in the list.
- Opening a conflict copy shows the content in **read-only** mode (title and body
  are not editable; save/pin/archive/folder controls are hidden).
- A **🗑️ Delete Conflict** button is shown in the toolbar; clicking it permanently
  removes the conflict copy after confirmation.

### Resolution workflow (recommended steps for the user)

1. When you see the conflict banner, click **View Conflicts**.
2. Open the conflict copy and compare it with the original note (open the original
   in another tab if needed).
3. Manually merge any content you want to keep into the original note.
4. Delete the conflict copy via the **🗑️ Delete Conflict** toolbar button.

### Guarantees

- **No silent data loss**: the server-side content at the time of conflict is
  always preserved in a conflict copy before being overwritten by the client.
- Conflict copies are **excluded** from the active, archived, and trashed note
  lists; they only appear in the dedicated Conflicts view.
- Conflict copies **do not** generate further conflict copies if edited (they
  are read-only in the UI).

---

## 3. Retention & Storage Notes

### Version cap

A maximum of **50 versions** is retained per note.  After every save,
`_prune_versions()` deletes the oldest snapshots beyond this limit.  The 50-version
cap keeps `note_versions` storage bounded regardless of how frequently a note is
edited.

**Estimated overhead per note at cap (50 versions):**

| Content | Bytes per version | 50 versions |
|---------|------------------|-------------|
| Title (avg 50 chars) | ~50 B | ~2.5 KB |
| Body (avg 2 000 chars) | ~2 KB | ~100 KB |
| Row overhead | ~50 B | ~2.5 KB |
| **Total** | **~2.1 KB** | **~105 KB** |

For a user with 1 000 notes all at the 50-version cap: ≈ 105 MB.  In practice
most notes are well under 2 000 characters and most notes never reach 50 versions.

### Conflict copies

Conflict copies are stored as normal `notes` rows (with `conflict_of IS NOT NULL`).
They do **not** accumulate version history of their own.  Users should resolve
and delete them promptly; the UI makes this easy via the dedicated Conflicts tab.

### Cascade deletes

Deleting a note permanently (`DELETE /api/notes/<id>/permanent`) cascades to:
- All rows in `note_versions` for that note (via `ON DELETE CASCADE`).
- All rows in `note_images` for that note (via `ON DELETE CASCADE`).

Conflict copies are **not** automatically deleted when the parent note is deleted
(the `FOREIGN KEY (conflict_of) REFERENCES notes(id)` has no cascade action).
This preserves the conflict-copy content even if the original note is deleted.

### Plesk / SQLite compatibility

- The `note_versions` table uses standard SQLite datatypes and constraints.
- The `conflict_of` column was added via `ALTER TABLE notes ADD COLUMN` in
  migration 005, which is safe on any SQLite version ≥ 3.0.
- No full-text search index, triggers, or stored procedures are used.
- The schema works unchanged on Plesk-hosted SQLite; no special database
  configuration is required.

### Retention strategy recommendation

For a personal notes app on a shared-hosting Plesk server:

- **Keep the 50-version cap** as is; increase to 100 if disk space permits.
- **Encourage users to resolve conflicts promptly** (the UI highlights them
  prominently).
- **Periodic backup**: back up `notes.db` daily (cron job or Plesk scheduled
  task).  The backup already recommended in `docs/deployment-notes.md` covers
  `note_versions` automatically because it is part of the same SQLite file.

---

## 4. Manual QA Checklist

> Copy these items into a new file `docs/qa-checklists/QA-M9-YYYY-MM-DD.md`
> for a release-day QA run.  Mark each ✅ Pass, ❌ Fail (with notes),
> or ⏭ Skip (with reason).

### M9-A: Version History Panel

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-A-01 | 🕐 (history) button is visible in the toolbar when a note is open | | |
| M9-A-02 | Clicking 🕐 opens the Version History side panel | | |
| M9-A-03 | A brand-new note shows "No versions saved yet" in the panel | | |
| M9-A-04 | Editing and saving a note creates one version in the panel | | |
| M9-A-05 | Versions are listed newest-first with date/time label | | |
| M9-A-06 | Each version shows a truncated title preview | | |
| M9-A-07 | Pressing Escape or clicking the backdrop closes the panel | | |
| M9-A-08 | Clicking ✕ in the panel header closes it | | |
| M9-A-09 | History button is hidden for trashed notes | | |
| M9-A-10 | History button is hidden for conflict copies | | |

### M9-B: Restore a Version

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-B-01 | Clicking **Restore** on a version shows a confirmation prompt | | |
| M9-B-02 | Cancelling the prompt leaves the note unchanged | | |
| M9-B-03 | Confirming restore updates the editor with the old content | | |
| M9-B-04 | After restore, the version list grows by one (current content was snapshotted) | | |
| M9-B-05 | The note list is refreshed to show the restored title | | |
| M9-B-06 | Autosave indicator shows "Restored ✓" briefly | | |

### M9-C: Version Retention

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-C-01 | Saving a note 55 times results in ≤ 50 versions in the panel | | |
| M9-C-02 | Oldest versions are pruned (newest 50 retained) | | |

### M9-D: Conflict Copy Creation

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-D-01 | Saving without `client_updated_at` does **not** create a conflict copy | | |
| M9-D-02 | Saving with matching `client_updated_at` does **not** create a conflict copy | | |
| M9-D-03 | Saving with a stale `client_updated_at` creates a conflict copy and shows the banner | | |
| M9-D-04 | Conflict copy title starts with `[Conflict Copy]` | | |
| M9-D-05 | Conflict copy body contains the server's previous content | | |
| M9-D-06 | The ⚠️ conflict banner appears at the bottom of the screen | | |
| M9-D-07 | **View Conflicts** in the banner switches to the Conflicts tab | | |
| M9-D-08 | **✕** in the banner dismisses it | | |

### M9-E: Conflict Copy Management

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-E-01 | **⚠ Conflicts** tab is visible in the sidebar | | |
| M9-E-02 | The Conflicts tab lists all conflict copies (⚠ prefix on each) | | |
| M9-E-03 | Conflict copies do **not** appear in the Notes / Archived / Trash tabs | | |
| M9-E-04 | Opening a conflict copy shows the content in read-only mode | | |
| M9-E-05 | Title and body are not editable in a conflict copy | | |
| M9-E-06 | Pin / Archive / Folder / Tag controls are hidden for conflict copies | | |
| M9-E-07 | 🕐 history button is hidden for conflict copies | | |
| M9-E-08 | **🗑️ Delete Conflict** button is visible for a conflict copy | | |
| M9-E-09 | Clicking **Delete Conflict** removes the copy from the list | | |
| M9-E-10 | Attempting to delete a normal note via `DELETE /api/conflicts/<id>` returns 404 | | |
| M9-E-11 | Folder section is hidden in the Conflicts view | | |

### M9-F: Security & Access Control

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-F-01 | `GET /api/notes/<id>/versions` returns 401/302 when not logged in | | |
| M9-F-02 | `GET /api/notes/<id>/versions` returns 404 for another user's note | | |
| M9-F-03 | `POST /api/notes/<id>/versions/<vid>/restore` returns 404 for a version belonging to a different note | | |
| M9-F-04 | `GET /api/conflicts` returns 401/302 when not logged in | | |
| M9-F-05 | `DELETE /api/conflicts/<id>` returns 401/302 when not logged in | | |

### M9-G: Regression (run alongside M9 QA)

| # | Check | Pass/Fail | Notes |
|---|---|---|---|
| M9-G-01 | Normal note create / edit / save still works as expected | | |
| M9-G-02 | Trash, restore from trash, and permanent delete still work | | |
| M9-G-03 | Archive / unarchive still works | | |
| M9-G-04 | Offline queue still flushes on reconnect (check with DevTools Network: Offline) | | |
| M9-G-05 | PDF export still produces a downloadable file | | |
| M9-G-06 | No JavaScript console errors on any page | | |
