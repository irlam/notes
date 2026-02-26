-- =============================================================================
-- Canonical MySQL 8+ Schema — Notes PWA
-- =============================================================================
-- Use this file for a FRESH install on a MySQL/MariaDB server.
-- For SQLite (local dev / Plesk SQLite), use schema.sql in the repo root.
--
-- Compatibility: MySQL 8.0+ / MariaDB 10.5+
-- Character set: utf8mb4 / utf8mb4_unicode_ci throughout
--
-- Usage:
--   mysql -u <user> -p <database> < db/schema.mysql.sql
--
-- For an EXISTING install, apply migrations/ files instead of re-running this.
-- =============================================================================

SET NAMES utf8mb4;
SET foreign_key_checks = 0;

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
    `id`            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    `username`      VARCHAR(150)    NOT NULL,
    `password_hash` VARCHAR(255)    NOT NULL,
    `is_active`     TINYINT(1)      NOT NULL DEFAULT 1,
    `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_users_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- folders
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `folders` (
    `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`    INT UNSIGNED NOT NULL,
    `name`       VARCHAR(100) NOT NULL,
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_folders_user_name` (`user_id`, `name`),
    KEY `idx_folders_user_id` (`user_id`),
    CONSTRAINT `fk_folders_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- tags
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `tags` (
    `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`    INT UNSIGNED NOT NULL,
    `name`       VARCHAR(50)  NOT NULL,
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_tags_user_name` (`user_id`, `name`),
    KEY `idx_tags_user_id` (`user_id`),
    CONSTRAINT `fk_tags_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- notes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `notes` (
    `id`          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`     INT UNSIGNED NOT NULL DEFAULT 1,
    `folder_id`   INT UNSIGNED,
    `title`       TEXT         NOT NULL,
    `body`        MEDIUMTEXT   NOT NULL,
    `is_pinned`   TINYINT(1)   NOT NULL DEFAULT 0,
    `is_archived` TINYINT(1)   NOT NULL DEFAULT 0,
    `is_trashed`  TINYINT(1)   NOT NULL DEFAULT 0,
    `conflict_of` INT UNSIGNED,
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_notes_user_id`    (`user_id`),
    KEY `idx_notes_folder_id`  (`folder_id`),
    KEY `idx_notes_conflict_of`(`conflict_of`),
    CONSTRAINT `fk_notes_user`        FOREIGN KEY (`user_id`)    REFERENCES `users`  (`id`),
    CONSTRAINT `fk_notes_folder`      FOREIGN KEY (`folder_id`)  REFERENCES `folders`(`id`),
    CONSTRAINT `fk_notes_conflict_of` FOREIGN KEY (`conflict_of`) REFERENCES `notes` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- note_tags  (junction)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `note_tags` (
    `note_id` INT UNSIGNED NOT NULL,
    `tag_id`  INT UNSIGNED NOT NULL,
    PRIMARY KEY (`note_id`, `tag_id`),
    KEY `idx_note_tags_note_id` (`note_id`),
    KEY `idx_note_tags_tag_id`  (`tag_id`),
    CONSTRAINT `fk_note_tags_note` FOREIGN KEY (`note_id`) REFERENCES `notes`(`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_note_tags_tag`  FOREIGN KEY (`tag_id`)  REFERENCES `tags` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- note_images
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `note_images` (
    `id`                INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    `note_id`           INT UNSIGNED  NOT NULL,
    `user_id`           INT UNSIGNED  NOT NULL,
    `filename`          VARCHAR(255)  NOT NULL,
    `original_filename` VARCHAR(255)  NOT NULL DEFAULT '',
    `mime_type`         VARCHAR(50)   NOT NULL DEFAULT 'image/jpeg',
    `file_size`         INT UNSIGNED  NOT NULL DEFAULT 0,
    `width`             SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    `height`            SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    `position`          SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    `annotation_data`   MEDIUMTEXT,
    `created_at`        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_note_images_filename` (`filename`),
    KEY `idx_note_images_note_id` (`note_id`),
    KEY `idx_note_images_user_id` (`user_id`),
    CONSTRAINT `fk_note_images_note` FOREIGN KEY (`note_id`) REFERENCES `notes`(`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_note_images_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- note_versions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `note_versions` (
    `id`       INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `note_id`  INT UNSIGNED NOT NULL,
    `user_id`  INT UNSIGNED NOT NULL,
    `title`    TEXT         NOT NULL,
    `body`     MEDIUMTEXT   NOT NULL,
    `saved_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_note_versions_note_id` (`note_id`),
    KEY `idx_note_versions_user_id` (`user_id`),
    CONSTRAINT `fk_note_versions_note` FOREIGN KEY (`note_id`) REFERENCES `notes`(`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_note_versions_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET foreign_key_checks = 1;
