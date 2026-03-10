-- Migration 009: add section_text column to note_images
-- Allows text to be stored between images (after each image, before the next).
-- Milestone 13

ALTER TABLE note_images ADD COLUMN section_text TEXT NOT NULL DEFAULT '';
