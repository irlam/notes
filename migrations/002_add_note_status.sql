-- Migration 002: Add note status columns (is_pinned, is_archived, is_trashed)
-- Run against an existing database that was created before Milestone 2.
ALTER TABLE notes ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0;
ALTER TABLE notes ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;
ALTER TABLE notes ADD COLUMN is_trashed INTEGER NOT NULL DEFAULT 0;
