-- Migration 001: Add users table
-- Run this against an existing database that was created without the users table.
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Backfill a placeholder row so existing notes (user_id=1) still resolve.
-- Replace the password_hash with a real value using: flask create-user
INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (1, 'admin', 'CHANGE_ME');
