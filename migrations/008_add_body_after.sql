-- Migration 008: Add body_after column to notes and note_versions for text-after-images support.
-- Applied to existing installs only. Fresh installs use schema.sql which already includes this.

ALTER TABLE notes ADD COLUMN body_after TEXT NOT NULL DEFAULT '';
ALTER TABLE note_versions ADD COLUMN body_after TEXT NOT NULL DEFAULT '';
