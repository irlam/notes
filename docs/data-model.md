# Data Model — Notes PWA

> **Database:** SQLite 3 (raw SQL, no ORM)  
> **Design principle:** Single-user-first, multi-user-ready  
> **No Docker** — database file lives on the Plesk server filesystem.

---

## Design Principles

1. **Single-user-first:** In v1 all rows belong to `user_id = 1` (a synthetic default user). No login is required.
2. **Multi-user-ready:** The `user_id` foreign key is present on every user-owned table from day one. Adding a `users` table and auth layer later requires no schema migration on existing tables beyond adding the FK constraint.
3. **No ORM:** All queries are written as raw SQL to keep the dependency surface small and to match the Plesk/SQLite deployment target.
4. **Soft timestamps:** `created_at` and `updated_at` are stored as `DATETIME` (UTC, SQLite text affinity). `updated_at` is updated on every write.

---

## Current Schema (v0.1)

```sql
CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER  PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER  NOT NULL DEFAULT 1,
    title       TEXT     NOT NULL DEFAULT '',
    body        TEXT     NOT NULL DEFAULT '',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes (user_id);
```

### Column Notes

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Auto-incremented |
| `user_id` | INTEGER | Defaults to 1 (single-user mode); FK to `users.id` in future |
| `title` | TEXT | Empty string allowed (UI auto-generates a placeholder title) |
| `body` | TEXT | Plain text in v1; will store Markdown/HTML in M3 |
| `created_at` | DATETIME | Set once on INSERT; UTC via `CURRENT_TIMESTAMP` |
| `updated_at` | DATETIME | Updated on every PUT; used for list ordering and conflict resolution |

---

## Planned Schema Extensions

### M2 — Offline Sync Queue (client-side only)

The offline write queue lives in the browser's **IndexedDB** (not the server database). No server-side schema change required for M2.

IndexedDB object store (client):

```
Store: pending_writes
  - key:       note_id (integer)
  - value:     { note_id, title, body, queued_at }
  - index:     queued_at (for ordering)
```

### M3 — Media Attachments

```sql
CREATE TABLE IF NOT EXISTS media (
    id          INTEGER  PRIMARY KEY AUTOINCREMENT,
    note_id     INTEGER  NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    user_id     INTEGER  NOT NULL DEFAULT 1,
    filename    TEXT     NOT NULL,
    mime_type   TEXT     NOT NULL,
    size_bytes  INTEGER  NOT NULL,
    annotation  TEXT,          -- SVG or JSON overlay data (nullable)
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_media_note_id ON media (note_id);
```

> **Open decision OD-3:** Whether to store file data as a filesystem path (recommended) or as a SQLite BLOB.

### M4 — Tags

```sql
CREATE TABLE IF NOT EXISTS tags (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    name    TEXT    NOT NULL,
    colour  TEXT    NOT NULL DEFAULT '#808080',
    UNIQUE (user_id, name)
);

CREATE TABLE IF NOT EXISTS note_tags (
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (note_id, tag_id)
);
```

### M5+ — Users & Auth

```sql
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    email         TEXT     NOT NULL UNIQUE,
    password_hash TEXT     NOT NULL,   -- bcrypt
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at DATETIME
);
```

When users are introduced, `DEFAULT 1` on `user_id` columns will be replaced with a proper FK constraint and the value populated from the session.

---

## Entity Relationship Diagram (planned full schema)

```
users
  └─< notes
          └─< media
          └─< note_tags >─ tags
```

- One user → many notes
- One note → many media attachments
- One note → many tags (via junction table)
- One tag → many notes (via junction table)

---

## Migration Strategy

- Schema changes are applied via numbered SQL migration files: `migrations/001_initial.sql`, `migrations/002_media.sql`, etc.
- The app checks the current schema version on startup (stored in SQLite `PRAGMA user_version`).
- In v1, `schema.sql` is applied once on first run if the database file does not exist.

---

## Open Decisions (Data Model)

| # | Question | Options | Decision |
|---|---|---|---|
| OD-3 | Image storage | Filesystem path vs SQLite BLOB | **TBD** (filesystem path preferred) |
| OD-5 | Annotation format | SVG string in `annotation` TEXT column vs merged PNG file | **TBD** |
