# Migrations

SQL migration files applied after the initial `schema.sql` is created.

## Naming Convention

```
NNN_short_description.sql
```

Where `NNN` is a zero-padded three-digit sequence number (e.g. `001`, `002`).

## How to Apply

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

## Schema Version Tracking

The current schema version is stored in SQLite `PRAGMA user_version`. Future tooling
will read this value on startup to determine which migrations to apply automatically.

## Current Migrations

| File | Description | Milestone |
|---|---|---|
| `001_add_users.sql` | Add users table; backfill placeholder admin row | Milestone 1 |
| `002_add_note_status.sql` | Add `is_pinned`, `is_archived`, `is_trashed` columns to notes | Milestone 2 |
