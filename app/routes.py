from flask import Blueprint, jsonify, request, render_template, abort
from .database import get_db

bp = Blueprint('main', __name__)

USER_ID = 1


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/api/notes', methods=['GET'])
def list_notes():
    db = get_db()
    rows = db.execute(
        'SELECT id, title, body, created_at, updated_at FROM notes '
        'WHERE user_id = ? ORDER BY updated_at DESC',
        (USER_ID,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route('/api/notes', methods=['POST'])
def create_note():
    data = request.get_json(silent=True) or {}
    title = data.get('title', '')
    body = data.get('body', '')
    db = get_db()
    cur = db.execute(
        'INSERT INTO notes (user_id, title, body) VALUES (?, ?, ?)',
        (USER_ID, title, body)
    )
    db.commit()
    row = db.execute(
        'SELECT id, title, body, created_at, updated_at FROM notes WHERE id = ?',
        (cur.lastrowid,)
    ).fetchone()
    return jsonify(dict(row)), 201


@bp.route('/api/notes/<int:note_id>', methods=['GET'])
def get_note(note_id):
    db = get_db()
    row = db.execute(
        'SELECT id, title, body, created_at, updated_at FROM notes WHERE id = ? AND user_id = ?',
        (note_id, USER_ID)
    ).fetchone()
    if row is None:
        abort(404)
    return jsonify(dict(row))


@bp.route('/api/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    db = get_db()
    existing = db.execute(
        'SELECT id FROM notes WHERE id = ? AND user_id = ?', (note_id, USER_ID)
    ).fetchone()
    if existing is None:
        abort(404)
    data = request.get_json(silent=True) or {}
    title = data.get('title', '')
    body = data.get('body', '')
    db.execute(
        'UPDATE notes SET title = ?, body = ?, updated_at = CURRENT_TIMESTAMP '
        'WHERE id = ? AND user_id = ?',
        (title, body, note_id, USER_ID)
    )
    db.commit()
    row = db.execute(
        'SELECT id, title, body, created_at, updated_at FROM notes WHERE id = ?',
        (note_id,)
    ).fetchone()
    return jsonify(dict(row))


@bp.route('/api/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    db = get_db()
    existing = db.execute(
        'SELECT id FROM notes WHERE id = ? AND user_id = ?', (note_id, USER_ID)
    ).fetchone()
    if existing is None:
        abort(404)
    db.execute('DELETE FROM notes WHERE id = ? AND user_id = ?', (note_id, USER_ID))
    db.commit()
    return '', 204


@bp.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@bp.errorhandler(400)
def bad_request(e):
    return jsonify({'error': 'Bad request'}), 400
