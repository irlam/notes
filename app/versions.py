"""Version history and conflict copy management (Milestone 9)."""

from flask import Blueprint, jsonify, request, abort, session
from .auth import login_required
from .database import get_db

versions_bp = Blueprint('versions', __name__)

_MAX_VERSIONS_PER_NOTE = 50
_NOTE_FIELDS = 'id, title, body, is_pinned, is_archived, is_trashed, folder_id, conflict_of, created_at, updated_at'


def _current_user_id():
    return session['user_id']


def _note_to_dict(row, tags=None):
    d = dict(row)
    d['tags'] = tags or []
    return d


# ---------------------------------------------------------------------------
# Version history
# ---------------------------------------------------------------------------

@versions_bp.route('/api/notes/<int:note_id>/versions', methods=['GET'])
@login_required
def list_versions(note_id):
    """Return version history for a note (newest first)."""
    db = get_db()
    if not db.execute(
        'SELECT id FROM notes WHERE id = ? AND user_id = ?',
        (note_id, _current_user_id())
    ).fetchone():
        abort(404)
    rows = db.execute(
        'SELECT id, note_id, title, saved_at FROM note_versions '
        'WHERE note_id = ? AND user_id = ? ORDER BY saved_at DESC, id DESC',
        (note_id, _current_user_id())
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@versions_bp.route('/api/notes/<int:note_id>/versions/<int:version_id>/restore', methods=['POST'])
@login_required
def restore_version(note_id, version_id):
    """Restore a note to a previous version.

    Before restoring, the current content is saved as a new version so the
    user can always undo the restore.
    """
    db = get_db()
    uid = _current_user_id()
    note = db.execute(
        f'SELECT {_NOTE_FIELDS} FROM notes WHERE id = ? AND user_id = ? AND is_trashed = 0',
        (note_id, uid)
    ).fetchone()
    if note is None:
        abort(404)
    version = db.execute(
        'SELECT id, title, body FROM note_versions WHERE id = ? AND note_id = ? AND user_id = ?',
        (version_id, note_id, uid)
    ).fetchone()
    if version is None:
        abort(404)

    # Snapshot current content before restoring
    _snapshot(db, note_id, uid, note['title'], note['body'])

    # Apply the historical version
    db.execute(
        'UPDATE notes SET title = ?, body = ?, updated_at = CURRENT_TIMESTAMP '
        'WHERE id = ? AND user_id = ?',
        (version['title'], version['body'], note_id, uid)
    )
    db.commit()
    _prune_versions(db, note_id, uid)

    updated = db.execute(
        f'SELECT {_NOTE_FIELDS} FROM notes WHERE id = ?', (note_id,)
    ).fetchone()
    return jsonify(_note_to_dict(updated))


# ---------------------------------------------------------------------------
# Conflict copies
# ---------------------------------------------------------------------------

@versions_bp.route('/api/conflicts', methods=['GET'])
@login_required
def list_conflicts():
    """Return all conflict copies belonging to the current user."""
    db = get_db()
    rows = db.execute(
        'SELECT id, title, body, conflict_of, created_at, updated_at '
        'FROM notes WHERE user_id = ? AND conflict_of IS NOT NULL '
        'ORDER BY updated_at DESC',
        (_current_user_id(),)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@versions_bp.route('/api/conflicts/<int:conflict_id>', methods=['DELETE'])
@login_required
def delete_conflict(conflict_id):
    """Permanently delete a conflict copy."""
    db = get_db()
    existing = db.execute(
        'SELECT id FROM notes WHERE id = ? AND user_id = ? AND conflict_of IS NOT NULL',
        (conflict_id, _current_user_id())
    ).fetchone()
    if existing is None:
        abort(404)
    db.execute('DELETE FROM notes WHERE id = ? AND user_id = ?',
               (conflict_id, _current_user_id()))
    db.commit()
    return '', 204


# ---------------------------------------------------------------------------
# Helpers (also called from routes.py)
# ---------------------------------------------------------------------------

def _snapshot(db, note_id, user_id, title, body):
    """Insert a version snapshot for a note."""
    db.execute(
        'INSERT INTO note_versions (note_id, user_id, title, body) VALUES (?, ?, ?, ?)',
        (note_id, user_id, title, body)
    )


def _prune_versions(db, note_id, user_id):
    """Keep only the most recent MAX_VERSIONS_PER_NOTE versions."""
    rows = db.execute(
        'SELECT id FROM note_versions WHERE note_id = ? AND user_id = ? '
        'ORDER BY saved_at DESC, id DESC LIMIT -1 OFFSET ?',
        (note_id, user_id, _MAX_VERSIONS_PER_NOTE)
    ).fetchall()
    if rows:
        ids = [r['id'] for r in rows]
        placeholders = ','.join('?' * len(ids))
        db.execute(
            f'DELETE FROM note_versions WHERE id IN ({placeholders})', ids
        )
        db.commit()
