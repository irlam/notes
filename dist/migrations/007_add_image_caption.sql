-- Migration 007: Add caption column to note_images for image text/caption support.
-- Applied to existing installs only. Fresh installs use schema.sql which already includes this.

ALTER TABLE note_images ADD COLUMN caption TEXT NOT NULL DEFAULT '';
