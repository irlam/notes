# Migrations

SQL migration files applied to **existing installs** when the schema changes.
For a **fresh install**, use `schema.sql` (SQLite) or `db/schema.mysql.sql` (MySQL 8+) instead — this gives you the complete, up-to-date schema in a single step.

---

## Fresh Install vs Migration Path

| Scenario | What to do |
|---|---|
| **Fresh install** (no existing database) | Run `bash scripts/db_init.sh` or apply `schema.sql` directly. Do NOT run individual migration files; `schema.sql` already includes all changes. |
| **Existing install** | Apply only the migration file(s) that are newer than your current schema version (see table below). |
| **MySQL fresh install** | Apply `db/schema.mysql.sql` via `mysql`. |

---

## Naming Convention

```
NNN_short_description.sql
```

Where `NNN` is a zero-padded three-digit sequence number (e.g. `001`, `002`).

---

## How to Apply (existing install)

Apply a migration manually via SSH on the Plesk server:

```bash
cd /path/to/app_root
source venv/bin/activate
python3 -c "
import sqlite3, os
db_path = os.environ.get('DATABASE_PATH', 'notes.db')
db = sqlite3.connect(db_path)
with open('migrations/NNN_description.sql') as f:
    db.executescript(f.read())
db.close()
print('Migration applied.')
"
deactivate
```

---

## Schema Version Tracking

The current schema version is recorded by the highest migration number applied.
All migrations are idempotent (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`
where supported, or guarded by `SELECT` checks) so they are safe to re-run.

---

## Current Migrations

| File | Description | Milestone | Included in schema.sql |
|---|---|---|---|
| `001_add_users.sql` | Add users table | M1 | ✅ |
| `002_add_note_status.sql` | Add `is_pinned`, `is_archived`, `is_trashed` columns | M2 | ✅ |
| `003_add_folders_tags.sql` | Add `folders`, `tags`, `note_tags` tables; add `folder_id` to notes | M3 | ✅ |
| `004_add_images.sql` | Add `note_images` table | M4 | ✅ |
| `005_add_versions.sql` | Add `note_versions` table and `conflict_of` column on notes | M9 | ✅ |
| `006_add_user_email.sql` | Add `email` column to `users`; add `email_send_log` table | M10 | ✅ |
| `007_add_image_caption.sql` | Add `caption` column to `note_images` | M11 | ✅ |
| `008_add_body_after.sql` | Add `body_after` column to `notes` and `note_versions` for text-after-images | M12 | ✅ |
