import sqlite3
import os
import click
from flask import current_app, g
from werkzeug.security import generate_password_hash, check_password_hash


def get_db():
    if 'db' not in g:
        db_path = current_app.config['DATABASE_PATH']
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def _apply_pending_migrations(db):
    """Apply any schema migrations that are newer than the current user_version.

    Fresh installs get the full schema via schema.sql (user_version stays 0 until
    this function sets it).  Existing installs may have tables created by earlier
    migrations that are missing newer columns; those gaps are filled here.

    The SQLite PRAGMA user_version is used to track which migrations have been
    applied.  Each migration block below is idempotent: it checks for the
    presence of a column before adding it so the function is safe to re-run.
    """
    version = db.execute('PRAGMA user_version').fetchone()[0]

    if version < 7:
        # Migration 007: add caption column to note_images
        # (fresh installs already have it via schema.sql; existing installs may not)
        # PRAGMA table_info returns rows of (cid, name, type, notnull, dflt_value, pk)
        cols = {row[1] for row in db.execute('PRAGMA table_info(note_images)').fetchall()}
        if 'caption' not in cols:
            db.execute(
                "ALTER TABLE note_images ADD COLUMN caption TEXT NOT NULL DEFAULT ''"
            )
            db.commit()
        db.execute('PRAGMA user_version = 7')
        db.commit()


def init_db(app):
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.sql')
    with app.app_context():
        db = get_db()
        with open(schema_path, 'r') as f:
            db.executescript(f.read())
        db.commit()
        _apply_pending_migrations(db)


def get_user_by_username(username):
    """Return user row for *username* or None."""
    db = get_db()
    return db.execute(
        'SELECT id, username, password_hash, is_active FROM users WHERE username = ?',
        (username,)
    ).fetchone()


def get_user_by_id(user_id):
    """Return user row for *user_id* or None."""
    db = get_db()
    return db.execute(
        'SELECT id, username, is_active, email FROM users WHERE id = ?',
        (user_id,)
    ).fetchone()


def get_user_email(user_id):
    """Return the stored email address for *user_id*, or None."""
    db = get_db()
    row = db.execute('SELECT email FROM users WHERE id = ?', (user_id,)).fetchone()
    return row['email'] if row else None


def set_user_email(user_id, email):
    """Store *email* for *user_id*. Pass None to clear."""
    db = get_db()
    db.execute('UPDATE users SET email = ? WHERE id = ?', (email, user_id))
    db.commit()


def create_user(username, password):
    """Insert a new user and return the new row id."""
    password_hash = generate_password_hash(password)
    db = get_db()
    cur = db.execute(
        'INSERT INTO users (username, password_hash) VALUES (?, ?)',
        (username, password_hash)
    )
    db.commit()
    return cur.lastrowid


def verify_password(user_row, password):
    """Return True if *password* matches the stored hash."""
    return check_password_hash(user_row['password_hash'], password)
