from flask import Blueprint, jsonify, request, render_template, abort, session, redirect, url_for
from .auth import login_required
from .database import get_db, get_user_by_id

bp = Blueprint('main', __name__)

_NOTE_FIELDS = 'id, title, body, is_pinned, is_archived, is_trashed, folder_id, created_at, updated_at'


def _current_user_id():
    return session['user_id']


def _like(val):
    """Wrap *val* in LIKE wildcards.
    The pipe character is escaped first so that the |% and |_ sequences
    introduced next are not themselves double-escaped."""
    return '%' + val.replace('|', '||').replace('%', '|%').replace('_', '|_') + '%'


def _fetch_tags_for_notes(db, note_ids):
    """Return dict of note_id -> list of {id, name} tag objects."""
    if not note_ids:
        return {}
    placeholders = ','.join('?' * len(note_ids))
    tag_rows = db.execute(
        f'SELECT nt.note_id, t.id, t.name FROM note_tags nt '
        f'JOIN tags t ON t.id = nt.tag_id '
        f'WHERE nt.note_id IN ({placeholders}) ORDER BY t.name ASC',
        note_ids
    ).fetchall()
    result = {}
    for tr in tag_rows:
        result.setdefault(tr['note_id'], []).append({'id': tr['id'], 'name': tr['name']})
    return result


def _note_to_dict(row, tags_by_note):
    d = dict(row)
    d['tags'] = tags_by_note.get(row['id'], [])
    return d


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
    q = request.args.get('q', '').strip()
    folder_id = request.args.get('folder_id', type=int)
    tag_id = request.args.get('tag_id', type=int)
    sort = request.args.get('sort', 'updated_desc')

    db = get_db()
    uid = _current_user_id()

    conditions = ['n.user_id = ?']
    params = [uid]

    if filter_param == 'trashed':
        conditions.append('n.is_trashed = 1')
    elif filter_param == 'archived':
        conditions.append('n.is_archived = 1')
        conditions.append('n.is_trashed = 0')
    else:
        conditions.append('n.is_archived = 0')
        conditions.append('n.is_trashed = 0')

    if folder_id is not None:
        conditions.append('n.folder_id = ?')
        params.append(folder_id)

    if sort == 'title_asc':
        order = 'n.title ASC, n.updated_at DESC'
    elif sort == 'created_desc':
        order = 'n.created_at DESC'
    else:  # updated_desc (default)
        order = 'n.is_pinned DESC, n.updated_at DESC'

    where = ' AND '.join(conditions)

    if q or tag_id is not None:
        extra = ''
        if q:
            lq = _like(q)
            extra += " AND (n.title LIKE ? ESCAPE '|' OR n.body LIKE ? ESCAPE '|' OR t.name LIKE ? ESCAPE '|')"
            params.extend([lq, lq, lq])
        if tag_id is not None:
            extra += ' AND nt.tag_id = ?'
            params.append(tag_id)
        query = (
            'SELECT DISTINCT n.id, n.title, n.body, n.is_pinned, n.is_archived, '
            'n.is_trashed, n.folder_id, n.created_at, n.updated_at '
            'FROM notes n '
            'LEFT JOIN note_tags nt ON nt.note_id = n.id '
            'LEFT JOIN tags t ON t.id = nt.tag_id '
            f'WHERE {where}{extra} ORDER BY {order}'
        )
    else:
        query = (
            f'SELECT {_NOTE_FIELDS} FROM notes n '
            f'WHERE {where} ORDER BY {order}'
        )

    rows = db.execute(query, params).fetchall()
    note_ids = [r['id'] for r in rows]
    tags_by_note = _fetch_tags_for_notes(db, note_ids)
    return jsonify([_note_to_dict(r, tags_by_note) for r in rows])


@bp.route('/api/notes', methods=['POST'])
@login_required
def create_note():
    data = request.get_json(silent=True) or {}
    title = data.get('title', '')
    body = data.get('body', '')
    folder_id = None
    if 'folder_id' in data and data['folder_id'] is not None:
        folder_id = int(data['folder_id'])
        db = get_db()
        if not db.execute(
            'SELECT id FROM folders WHERE id = ? AND user_id = ?',
            (folder_id, _current_user_id())
        ).fetchone():
            abort(400)
    db = get_db()
    cur = db.execute(
        'INSERT INTO notes (user_id, title, body, folder_id) VALUES (?, ?, ?, ?)',
        (_current_user_id(), title, body, folder_id)
    )
    db.commit()
    row = db.execute(
        f'SELECT {_NOTE_FIELDS} FROM notes WHERE id = ?',
        (cur.lastrowid,)
    ).fetchone()
    d = dict(row)
    d['tags'] = []
    return jsonify(d), 201


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
    d = dict(row)
    d['tags'] = _fetch_tags_for_notes(db, [note_id]).get(note_id, [])
    return jsonify(d)


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

    if 'folder_id' in data:
        new_folder_id = data['folder_id']
        if new_folder_id is not None:
            new_folder_id = int(new_folder_id)
            if not db.execute(
                'SELECT id FROM folders WHERE id = ? AND user_id = ?',
                (new_folder_id, _current_user_id())
            ).fetchone():
                abort(400)
        db.execute(
            'UPDATE notes SET title = ?, body = ?, is_pinned = ?, folder_id = ?, '
            'updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?',
            (title, body, is_pinned, new_folder_id, note_id, _current_user_id())
        )
    else:
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
    d = dict(row)
    d['tags'] = _fetch_tags_for_notes(db, [note_id]).get(note_id, [])
    return jsonify(d)


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
    d = dict(updated)
    d['tags'] = _fetch_tags_for_notes(db, [note_id]).get(note_id, [])
    return jsonify(d)


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
    d = dict(updated)
    d['tags'] = _fetch_tags_for_notes(db, [note_id]).get(note_id, [])
    return jsonify(d)


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


@bp.route('/api/notes/<int:note_id>/tags', methods=['PUT'])
@login_required
def set_note_tags(note_id):
    """Replace all tags on a note. Body: {tag_ids: [1, 2, ...]}"""
    db = get_db()
    if not db.execute(
        'SELECT id FROM notes WHERE id = ? AND user_id = ?',
        (note_id, _current_user_id())
    ).fetchone():
        abort(404)
    data = request.get_json(silent=True) or {}
    tag_ids = data.get('tag_ids', [])
    if not isinstance(tag_ids, list):
        abort(400)
    # Validate all tag_ids belong to current user
    if tag_ids:
        placeholders = ','.join('?' * len(tag_ids))
        valid_rows = db.execute(
            f'SELECT id FROM tags WHERE id IN ({placeholders}) AND user_id = ?',
            [*tag_ids, _current_user_id()]
        ).fetchall()
        if len(valid_rows) != len(set(tag_ids)):
            abort(400)
    db.execute('DELETE FROM note_tags WHERE note_id = ?', (note_id,))
    for tid in tag_ids:
        db.execute('INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?, ?)',
                   (note_id, int(tid)))
    db.commit()
    return jsonify(_fetch_tags_for_notes(db, [note_id]).get(note_id, []))


# ---------------------------------------------------------------------------
# Folder CRUD
# ---------------------------------------------------------------------------

@bp.route('/api/folders', methods=['GET'])
@login_required
def list_folders():
    db = get_db()
    rows = db.execute(
        'SELECT id, name, created_at FROM folders WHERE user_id = ? ORDER BY name ASC',
        (_current_user_id(),)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route('/api/folders', methods=['POST'])
@login_required
def create_folder():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        abort(400)
    db = get_db()
    try:
        cur = db.execute(
            'INSERT INTO folders (user_id, name) VALUES (?, ?)',
            (_current_user_id(), name)
        )
        db.commit()
    except Exception:
        abort(400)
    row = db.execute(
        'SELECT id, name, created_at FROM folders WHERE id = ?', (cur.lastrowid,)
    ).fetchone()
    return jsonify(dict(row)), 201


@bp.route('/api/folders/<int:folder_id>', methods=['PUT'])
@login_required
def update_folder(folder_id):
    db = get_db()
    if not db.execute(
        'SELECT id FROM folders WHERE id = ? AND user_id = ?',
        (folder_id, _current_user_id())
    ).fetchone():
        abort(404)
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        abort(400)
    try:
        db.execute('UPDATE folders SET name = ? WHERE id = ? AND user_id = ?',
                   (name, folder_id, _current_user_id()))
        db.commit()
    except Exception:
        abort(400)
    row = db.execute(
        'SELECT id, name, created_at FROM folders WHERE id = ?', (folder_id,)
    ).fetchone()
    return jsonify(dict(row))


@bp.route('/api/folders/<int:folder_id>', methods=['DELETE'])
@login_required
def delete_folder(folder_id):
    db = get_db()
    if not db.execute(
        'SELECT id FROM folders WHERE id = ? AND user_id = ?',
        (folder_id, _current_user_id())
    ).fetchone():
        abort(404)
    # Unfile notes in this folder (keep notes, just remove folder association)
    db.execute('UPDATE notes SET folder_id = NULL WHERE folder_id = ? AND user_id = ?',
               (folder_id, _current_user_id()))
    db.execute('DELETE FROM folders WHERE id = ? AND user_id = ?',
               (folder_id, _current_user_id()))
    db.commit()
    return '', 204


# ---------------------------------------------------------------------------
# Tag CRUD
# ---------------------------------------------------------------------------

@bp.route('/api/tags', methods=['GET'])
@login_required
def list_tags():
    db = get_db()
    rows = db.execute(
        'SELECT id, name, created_at FROM tags WHERE user_id = ? ORDER BY name ASC',
        (_current_user_id(),)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route('/api/tags', methods=['POST'])
@login_required
def create_tag():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        abort(400)
    db = get_db()
    try:
        cur = db.execute(
            'INSERT INTO tags (user_id, name) VALUES (?, ?)',
            (_current_user_id(), name)
        )
        db.commit()
    except Exception:
        abort(400)
    row = db.execute(
        'SELECT id, name, created_at FROM tags WHERE id = ?', (cur.lastrowid,)
    ).fetchone()
    return jsonify(dict(row)), 201


@bp.route('/api/tags/<int:tag_id>', methods=['PUT'])
@login_required
def update_tag(tag_id):
    db = get_db()
    if not db.execute(
        'SELECT id FROM tags WHERE id = ? AND user_id = ?',
        (tag_id, _current_user_id())
    ).fetchone():
        abort(404)
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        abort(400)
    try:
        db.execute('UPDATE tags SET name = ? WHERE id = ? AND user_id = ?',
                   (name, tag_id, _current_user_id()))
        db.commit()
    except Exception:
        abort(400)
    row = db.execute(
        'SELECT id, name, created_at FROM tags WHERE id = ?', (tag_id,)
    ).fetchone()
    return jsonify(dict(row))


@bp.route('/api/tags/<int:tag_id>', methods=['DELETE'])
@login_required
def delete_tag(tag_id):
    db = get_db()
    if not db.execute(
        'SELECT id FROM tags WHERE id = ? AND user_id = ?',
        (tag_id, _current_user_id())
    ).fetchone():
        abort(404)
    # note_tags rows are removed by ON DELETE CASCADE
    db.execute('DELETE FROM tags WHERE id = ? AND user_id = ?',
               (tag_id, _current_user_id()))
    db.commit()
    return '', 204


@bp.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@bp.errorhandler(400)
def bad_request(e):
    return jsonify({'error': 'Bad request'}), 400
