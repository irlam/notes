from flask import Blueprint, jsonify, request, render_template, abort, session, redirect, url_for
from .auth import login_required
from .database import get_db, get_user_by_id

bp = Blueprint('main', __name__)

_NOTE_FIELDS = 'id, title, body, is_pinned, is_archived, is_trashed, created_at, updated_at'


def _current_user_id():
    return session['user_id']


@bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@bp.route('/dashboard')
@login_required
def dashboard():
    user = get_user_by_id(_current_user_id())
    return render_template('dashboard.html', username=user['username'] if user else '')


@bp.route('/api/notes', methods=['GET'])
@login_required
def list_notes():
    filter_param = request.args.get('filter', 'active')
    db = get_db()
    if filter_param == 'trashed':
        rows = db.execute(
            f'SELECT {_NOTE_FIELDS} FROM notes '
            'WHERE user_id = ? AND is_trashed = 1 ORDER BY updated_at DESC',
            (_current_user_id(),)
        ).fetchall()
    elif filter_param == 'archived':
        rows = db.execute(
            f'SELECT {_NOTE_FIELDS} FROM notes '
            'WHERE user_id = ? AND is_archived = 1 AND is_trashed = 0 '
            'ORDER BY updated_at DESC',
            (_current_user_id(),)
        ).fetchall()
    else:
        # Active: not archived and not trashed; pinned notes first
        rows = db.execute(
            f'SELECT {_NOTE_FIELDS} FROM notes '
            'WHERE user_id = ? AND is_archived = 0 AND is_trashed = 0 '
            'ORDER BY is_pinned DESC, updated_at DESC',
            (_current_user_id(),)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route('/api/notes', methods=['POST'])
@login_required
def create_note():
    data = request.get_json(silent=True) or {}
    title = data.get('title', '')
    body = data.get('body', '')
    db = get_db()
    cur = db.execute(
        'INSERT INTO notes (user_id, title, body) VALUES (?, ?, ?)',
        (_current_user_id(), title, body)
    )
    db.commit()
    row = db.execute(
        f'SELECT {_NOTE_FIELDS} FROM notes WHERE id = ?',
        (cur.lastrowid,)
    ).fetchone()
    return jsonify(dict(row)), 201


@bp.route('/api/notes/<int:note_id>', methods=['GET'])
@login_required
def get_note(note_id):
    db = get_db()
    row = db.execute(
        f'SELECT {_NOTE_FIELDS} FROM notes WHERE id = ? AND user_id = ?',
        (note_id, _current_user_id())
    ).fetchone()
    if row is None:
        abort(404)
    return jsonify(dict(row))


@bp.route('/api/notes/<int:note_id>', methods=['PUT'])
@login_required
def update_note(note_id):
    db = get_db()
    existing = db.execute(
        'SELECT id FROM notes WHERE id = ? AND user_id = ?', (note_id, _current_user_id())
    ).fetchone()
    if existing is None:
        abort(404)
    data = request.get_json(silent=True) or {}
    title = data.get('title', '')
    body = data.get('body', '')
    is_pinned = int(bool(data.get('is_pinned', 0)))
    db.execute(
        'UPDATE notes SET title = ?, body = ?, is_pinned = ?, updated_at = CURRENT_TIMESTAMP '
        'WHERE id = ? AND user_id = ?',
        (title, body, is_pinned, note_id, _current_user_id())
    )
    db.commit()
    row = db.execute(
        f'SELECT {_NOTE_FIELDS} FROM notes WHERE id = ?',
        (note_id,)
    ).fetchone()
    return jsonify(dict(row))


@bp.route('/api/notes/<int:note_id>/archive', methods=['POST'])
@login_required
def archive_note(note_id):
    """Toggle archive status (unarchives if already archived)."""
    db = get_db()
    row = db.execute(
        'SELECT id, is_archived FROM notes WHERE id = ? AND user_id = ? AND is_trashed = 0',
        (note_id, _current_user_id())
    ).fetchone()
    if row is None:
        abort(404)
    new_val = 0 if row['is_archived'] else 1
    db.execute(
        'UPDATE notes SET is_archived = ?, updated_at = CURRENT_TIMESTAMP '
        'WHERE id = ? AND user_id = ?',
        (new_val, note_id, _current_user_id())
    )
    db.commit()
    updated = db.execute(
        f'SELECT {_NOTE_FIELDS} FROM notes WHERE id = ?', (note_id,)
    ).fetchone()
    return jsonify(dict(updated))


@bp.route('/api/notes/<int:note_id>/restore', methods=['POST'])
@login_required
def restore_note(note_id):
    """Restore a trashed note back to active."""
    db = get_db()
    row = db.execute(
        'SELECT id FROM notes WHERE id = ? AND user_id = ? AND is_trashed = 1',
        (note_id, _current_user_id())
    ).fetchone()
    if row is None:
        abort(404)
    db.execute(
        'UPDATE notes SET is_trashed = 0, updated_at = CURRENT_TIMESTAMP '
        'WHERE id = ? AND user_id = ?',
        (note_id, _current_user_id())
    )
    db.commit()
    updated = db.execute(
        f'SELECT {_NOTE_FIELDS} FROM notes WHERE id = ?', (note_id,)
    ).fetchone()
    return jsonify(dict(updated))


@bp.route('/api/notes/<int:note_id>', methods=['DELETE'])
@login_required
def trash_note(note_id):
    """Move note to trash (soft delete)."""
    db = get_db()
    existing = db.execute(
        'SELECT id FROM notes WHERE id = ? AND user_id = ?', (note_id, _current_user_id())
    ).fetchone()
    if existing is None:
        abort(404)
    db.execute(
        'UPDATE notes SET is_trashed = 1, updated_at = CURRENT_TIMESTAMP '
        'WHERE id = ? AND user_id = ?',
        (note_id, _current_user_id())
    )
    db.commit()
    return '', 204


@bp.route('/api/notes/<int:note_id>/permanent', methods=['DELETE'])
@login_required
def delete_note_permanent(note_id):
    """Permanently delete a note (must be in trash first)."""
    db = get_db()
    existing = db.execute(
        'SELECT id FROM notes WHERE id = ? AND user_id = ? AND is_trashed = 1',
        (note_id, _current_user_id())
    ).fetchone()
    if existing is None:
        abort(404)
    db.execute(
        'DELETE FROM notes WHERE id = ? AND user_id = ?',
        (note_id, _current_user_id())
    )
    db.commit()
    return '', 204


@bp.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@bp.errorhandler(400)
def bad_request(e):
    return jsonify({'error': 'Bad request'}), 400
