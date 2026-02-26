import os
import uuid
from flask import Blueprint, request, jsonify, abort, send_file, session, current_app
from .auth import login_required
from .database import get_db

media_bp = Blueprint('media', __name__)

_ALLOWED_MIME = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
_EXT_TO_MIME = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
}
_MAX_BYTES = 10 * 1024 * 1024   # 10 MB pre-compression
_MAX_DIMENSION = 1920


def _current_user_id():
    return session['user_id']


def _media_dir():
    return current_app.config['MEDIA_PATH']


def _get_note_for_user(db, note_id, user_id):
    return db.execute(
        'SELECT id FROM notes WHERE id = ? AND user_id = ?',
        (note_id, user_id)
    ).fetchone()


def _compress_image(data, mime_type):
    """Resize and compress an image with Pillow.

    Returns (compressed_bytes, final_mime_type, file_extension, width, height).
    Falls back to storing the raw bytes unchanged if Pillow is unavailable.
    """
    try:
        import io
        from PIL import Image, ImageOps

        img = Image.open(io.BytesIO(data))

        # Honour EXIF orientation before any other processing
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # Resize to fit within _MAX_DIMENSION x _MAX_DIMENSION
        w, h = img.size
        if w > _MAX_DIMENSION or h > _MAX_DIMENSION:
            img.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION), Image.LANCZOS)
        w, h = img.size

        buf = io.BytesIO()
        if mime_type == 'image/png':
            img = img.convert('RGBA')
            img.save(buf, format='PNG', optimize=True)
            final_mime = 'image/png'
            ext = 'png'
        elif mime_type == 'image/gif':
            # Keep GIF data unchanged (animation support)
            buf.write(data)
            final_mime = 'image/gif'
            ext = 'gif'
        elif mime_type == 'image/webp':
            img = img.convert('RGB')
            img.save(buf, format='WEBP', quality=85, method=4)
            final_mime = 'image/webp'
            ext = 'webp'
        else:
            img = img.convert('RGB')
            img.save(buf, format='JPEG', quality=85, optimize=True)
            final_mime = 'image/jpeg'
            ext = 'jpg'

        return buf.getvalue(), final_mime, ext, w, h

    except ImportError:
        # Pillow not installed – store raw without compression
        ext_map = {
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'image/gif': 'gif',
            'image/webp': 'webp',
        }
        ext = ext_map.get(mime_type, 'jpg')
        return data, mime_type, ext, 0, 0


def _image_to_dict(row):
    d = dict(row)
    d['url'] = f'/media/{d["filename"]}'
    return d


# ---------------------------------------------------------------------------
# List images for a note
# ---------------------------------------------------------------------------

@media_bp.route('/api/notes/<int:note_id>/images', methods=['GET'])
@login_required
def list_images(note_id):
    db = get_db()
    if not _get_note_for_user(db, note_id, _current_user_id()):
        abort(404)
    rows = db.execute(
        'SELECT id, filename, original_filename, mime_type, file_size, '
        'width, height, position, annotation_data, created_at '
        'FROM note_images WHERE note_id = ? AND user_id = ? '
        'ORDER BY position ASC, id ASC',
        (note_id, _current_user_id())
    ).fetchall()
    return jsonify([_image_to_dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Upload image to a note
# ---------------------------------------------------------------------------

@media_bp.route('/api/notes/<int:note_id>/images', methods=['POST'])
@login_required
def upload_image(note_id):
    db = get_db()
    if not _get_note_for_user(db, note_id, _current_user_id()):
        abort(404)

    if 'image' not in request.files:
        abort(400)
    f = request.files['image']
    if not f or not f.filename:
        abort(400)

    # Determine MIME type – try reported MIME first, then extension
    mime_type = (f.mimetype or '').lower()
    if mime_type not in _ALLOWED_MIME:
        ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
        mime_type = _EXT_TO_MIME.get(ext, '')
        if not mime_type:
            abort(400)

    data = f.read()
    if len(data) == 0:
        abort(400)
    if len(data) > _MAX_BYTES:
        abort(413)

    compressed, final_mime, ext, width, height = _compress_image(data, mime_type)

    # Persist to disk
    media_dir = _media_dir()
    os.makedirs(media_dir, exist_ok=True)
    server_filename = f'{uuid.uuid4().hex}.{ext}'
    filepath = os.path.join(media_dir, server_filename)
    with open(filepath, 'wb') as fh:
        fh.write(compressed)

    # Next position after existing images
    row = db.execute(
        'SELECT COALESCE(MAX(position), -1) FROM note_images WHERE note_id = ?',
        (note_id,)
    ).fetchone()
    next_pos = (row[0] if row else -1) + 1

    original_filename = f.filename or ''
    cur = db.execute(
        'INSERT INTO note_images '
        '(note_id, user_id, filename, original_filename, mime_type, '
        'file_size, width, height, position) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (note_id, _current_user_id(), server_filename, original_filename,
         final_mime, len(compressed), width, height, next_pos)
    )
    db.commit()

    new_row = db.execute(
        'SELECT id, filename, original_filename, mime_type, file_size, '
        'width, height, position, annotation_data, created_at '
        'FROM note_images WHERE id = ?',
        (cur.lastrowid,)
    ).fetchone()
    return jsonify(_image_to_dict(new_row)), 201


# ---------------------------------------------------------------------------
# Delete an image from a note
# ---------------------------------------------------------------------------

@media_bp.route('/api/notes/<int:note_id>/images/<int:image_id>', methods=['DELETE'])
@login_required
def delete_image(note_id, image_id):
    db = get_db()
    row = db.execute(
        'SELECT id, filename FROM note_images '
        'WHERE id = ? AND note_id = ? AND user_id = ?',
        (image_id, note_id, _current_user_id())
    ).fetchone()
    if not row:
        abort(404)

    filepath = os.path.join(_media_dir(), row['filename'])
    try:
        os.remove(filepath)
    except OSError:
        pass  # File may already be missing; proceed with DB deletion

    db.execute('DELETE FROM note_images WHERE id = ?', (image_id,))
    db.commit()
    return '', 204


# ---------------------------------------------------------------------------
# Reorder images for a note
# ---------------------------------------------------------------------------

@media_bp.route('/api/notes/<int:note_id>/images/reorder', methods=['PUT'])
@login_required
def reorder_images(note_id):
    db = get_db()
    if not _get_note_for_user(db, note_id, _current_user_id()):
        abort(404)

    data = request.get_json(silent=True) or {}
    image_ids = data.get('image_ids', [])
    if not isinstance(image_ids, list):
        abort(400)

    for pos, img_id in enumerate(image_ids):
        db.execute(
            'UPDATE note_images SET position = ? '
            'WHERE id = ? AND note_id = ? AND user_id = ?',
            (pos, int(img_id), note_id, _current_user_id())
        )
    db.commit()

    rows = db.execute(
        'SELECT id, filename, original_filename, mime_type, file_size, '
        'width, height, position, annotation_data, created_at '
        'FROM note_images WHERE note_id = ? AND user_id = ? '
        'ORDER BY position ASC, id ASC',
        (note_id, _current_user_id())
    ).fetchall()
    return jsonify([_image_to_dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Save annotation data for an image
# ---------------------------------------------------------------------------

@media_bp.route('/api/notes/<int:note_id>/images/<int:image_id>', methods=['PUT'])
@login_required
def update_image(note_id, image_id):
    import json as _json
    db = get_db()
    row = db.execute(
        'SELECT id FROM note_images WHERE id = ? AND note_id = ? AND user_id = ?',
        (image_id, note_id, _current_user_id())
    ).fetchone()
    if not row:
        abort(404)

    data = request.get_json(silent=True) or {}
    if 'annotation_data' not in data:
        abort(400)

    annotation_data = data['annotation_data']
    if annotation_data is not None:
        if isinstance(annotation_data, (dict, list)):
            annotation_data = _json.dumps(annotation_data)
        elif isinstance(annotation_data, str):
            try:
                _json.loads(annotation_data)
            except ValueError:
                abort(400)
        else:
            abort(400)

    db.execute(
        'UPDATE note_images SET annotation_data = ? WHERE id = ?',
        (annotation_data, image_id)
    )
    db.commit()

    updated = db.execute(
        'SELECT id, filename, original_filename, mime_type, file_size, '
        'width, height, position, annotation_data, created_at '
        'FROM note_images WHERE id = ?',
        (image_id,)
    ).fetchone()
    return jsonify(_image_to_dict(updated))


# ---------------------------------------------------------------------------
# Serve a media file (only to the owning user)
# ---------------------------------------------------------------------------

@media_bp.route('/media/<path:filename>', methods=['GET'])
@login_required
def serve_media(filename):
    # Reject any path traversal attempts
    if '/' in filename or '\\' in filename or '..' in filename:
        abort(404)

    db = get_db()
    row = db.execute(
        'SELECT id FROM note_images WHERE filename = ? AND user_id = ?',
        (filename, _current_user_id())
    ).fetchone()
    if not row:
        abort(404)

    filepath = os.path.join(_media_dir(), filename)
    if not os.path.isfile(filepath):
        abort(404)

    return send_file(filepath)
