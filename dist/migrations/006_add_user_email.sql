-- Migration 006: Add email column to users table and email_send_log table for M10 rate limiting.
-- Applied to existing installs only. Fresh installs use schema.sql which already includes these.

ALTER TABLE users ADD COLUMN email TEXT;

CREATE TABLE IF NOT EXISTS email_send_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    note_id INTEGER NOT NULL,
    sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_email_send_log_user_id ON email_send_log (user_id);
