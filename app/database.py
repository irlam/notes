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


def init_db(app):
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.sql')
    with app.app_context():
        db = get_db()
        with open(schema_path, 'r') as f:
            db.executescript(f.read())
        db.commit()


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
