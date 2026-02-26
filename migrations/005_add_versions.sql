-- Migration 005: Add note_versions table and conflict_of column for Milestone 9
-- (Version history and conflict copy management)

CREATE TABLE IF NOT EXISTS note_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    saved_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES notes (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS idx_note_versions_note_id ON note_versions (note_id);
CREATE INDEX IF NOT EXISTS idx_note_versions_user_id ON note_versions (user_id);

-- conflict_of: NULL = normal note; non-NULL = conflict copy of that note id
ALTER TABLE notes ADD COLUMN conflict_of INTEGER;
CREATE INDEX IF NOT EXISTS idx_notes_conflict_of ON notes (conflict_of);
