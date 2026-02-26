"""Tests for Milestone 7: Single-note PDF export."""
import io
import json
import os
import tempfile
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-abcdef1234567890')

# ---------------------------------------------------------------------------
# Minimal valid JPEG (reused from earlier milestones)
# ---------------------------------------------------------------------------
_TINY_JPEG = (
    b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
    b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
    b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e\xbf'
    b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
    b'\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b'
    b'\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04'
    b'\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa'
    b'\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br'
    b'\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZ'
    b'cdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94'
    b'\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa'
    b'\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7'
    b'\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3'
    b'\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8'
    b'\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xf4\xff\xd9'
)

_SAMPLE_ANNOTATION = {
    'version': 1,
    'strokes': [
        {
            'tool': 'pen',
            'color': '#e74c3c',
            'width': 0.006,
            'opacity': 1.0,
            'points': [{'x': 0.1, 'y': 0.2}, {'x': 0.15, 'y': 0.25}],
        },
        {
            'tool': 'arrow',
            'color': '#0000ff',
            'width': 0.006,
            'opacity': 1.0,
            'x1': 0.1, 'y1': 0.2, 'x2': 0.5, 'y2': 0.6,
        },
        {
            'tool': 'rectangle',
            'color': '#00aa00',
            'width': 0.004,
            'opacity': 0.8,
            'x1': 0.2, 'y1': 0.2, 'x2': 0.8, 'y2': 0.8,
        },
        {
            'tool': 'circle',
            'color': '#ffcc00',
            'width': 0.004,
            'opacity': 0.9,
            'x1': 0.3, 'y1': 0.3, 'x2': 0.7, 'y2': 0.7,
        },
        {
            'tool': 'text',
            'color': '#000000',
            'width': 0.006,
            'opacity': 1.0,
            'x': 0.2, 'y': 0.5,
            'text': 'Hello',
        },
    ],
}


@pytest.fixture()
def app(tmp_path):
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    media_path = str(tmp_path / 'uploads')

    os.environ['SECRET_KEY'] = 'test-secret-key-abcdef1234567890'
    os.environ['DATABASE_PATH'] = db_path
    os.environ['MEDIA_PATH'] = media_path

    from app import create_app
    application = create_app()
    application.config['TESTING'] = True
    application.config['SESSION_COOKIE_SECURE'] = False

    with application.app_context():
        from app.database import create_user
        create_user('alice', 'correct-horse-battery')

    yield application

    os.unlink(db_path)
    os.environ.pop('MEDIA_PATH', None)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    client.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
    return client


def _note(auth_client, title='Test Note', body='Hello world'):
    return auth_client.post('/api/notes', json={'title': title, 'body': body}).get_json()


def _upload(auth_client, note_id):
    return auth_client.post(
        f'/api/notes/{note_id}/images',
        data={'image': (io.BytesIO(_TINY_JPEG), 'photo.jpg', 'image/jpeg')},
        content_type='multipart/form-data',
    ).get_json()


# ---------------------------------------------------------------------------
# Authentication guard
# ---------------------------------------------------------------------------

class TestPdfExportAuth:
    def test_requires_login(self, client):
        r = client.get('/api/notes/1/export.pdf')
        assert r.status_code == 302  # redirect to login

    def test_wrong_user_returns_404(self, app):
        """A user cannot export another user's note."""
        with app.app_context():
            from app.database import create_user
            create_user('bob', 'password-for-bob')

        c = app.test_client()
        c.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
        note = c.post('/api/notes', json={'title': 'Alice', 'body': ''}).get_json()
        c.post('/logout')

        c.post('/login', data={'username': 'bob', 'password': 'password-for-bob'})
        r = c.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 404

    def test_nonexistent_note_returns_404(self, auth_client):
        r = auth_client.get('/api/notes/99999/export.pdf')
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

class TestPdfExportResponse:
    def test_returns_200(self, auth_client):
        note = _note(auth_client)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200

    def test_content_type_is_pdf(self, auth_client):
        note = _note(auth_client)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.content_type == 'application/pdf'

    def test_response_starts_with_pdf_header(self, auth_client):
        note = _note(auth_client)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.data[:4] == b'%PDF'

    def test_content_disposition_attachment(self, auth_client):
        note = _note(auth_client)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        cd = r.headers.get('Content-Disposition', '')
        assert 'attachment' in cd

    def test_filename_in_content_disposition(self, auth_client):
        note = _note(auth_client, title='My Note')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        cd = r.headers.get('Content-Disposition', '')
        assert '.pdf' in cd

    def test_pdf_is_non_empty(self, auth_client):
        note = _note(auth_client)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert len(r.data) > 100


# ---------------------------------------------------------------------------
# Content — text only
# ---------------------------------------------------------------------------

class TestPdfExportContent:
    def test_untitled_note(self, auth_client):
        note = _note(auth_client, title='', body='')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'

    def test_note_with_body_text(self, auth_client):
        note = _note(auth_client, title='Body Test',
                     body='Line one\nLine two\nLine three')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'

    def test_note_with_checklist_items(self, auth_client):
        body = '[ ] Buy milk\n[x] Write tests\n[ ] Deploy'
        note = _note(auth_client, title='Checklist', body=body)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'

    def test_note_with_mixed_content(self, auth_client):
        body = 'Intro\n\n[ ] Task 1\n[x] Task 2\n\nConclusion'
        note = _note(auth_client, title='Mixed', body=body)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200

    def test_note_with_html_special_chars(self, auth_client):
        note = _note(auth_client, title='<Alert>', body='x & y > z')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'

    def test_export_does_not_mutate_note(self, auth_client):
        note = _note(auth_client, title='Original', body='Body')
        auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        r = auth_client.get(f'/api/notes/{note["id"]}')
        updated = r.get_json()
        assert updated['title'] == 'Original'
        assert updated['body'] == 'Body'


# ---------------------------------------------------------------------------
# Content — with images
# ---------------------------------------------------------------------------

class TestPdfExportWithImages:
    def test_note_with_image(self, auth_client):
        note = _note(auth_client, title='With Image', body='See below')
        _upload(auth_client, note['id'])
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'

    def test_note_with_multiple_images(self, auth_client):
        note = _note(auth_client, title='Multi', body='')
        _upload(auth_client, note['id'])
        _upload(auth_client, note['id'])
        _upload(auth_client, note['id'])
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'

    def test_note_with_annotated_image(self, auth_client):
        note = _note(auth_client, title='Annotated', body='')
        img = _upload(auth_client, note['id'])
        # Save annotation data
        auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'annotation_data': json.dumps(_SAMPLE_ANNOTATION)},
        )
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'

    def test_note_image_only_no_body(self, auth_client):
        note = _note(auth_client, title='Image Only', body='')
        _upload(auth_client, note['id'])
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Annotation compositing unit tests
# ---------------------------------------------------------------------------

class TestAnnotationCompositing:
    def test_composite_no_annotation_returns_jpeg(self, tmp_path):
        from app.pdf import _composite_annotations
        img_path = str(tmp_path / 'test.jpg')
        with open(img_path, 'wb') as f:
            f.write(_TINY_JPEG)
        # None annotation_data → treated as empty strokes, returns JPEG bytes
        result = _composite_annotations(img_path, None)
        assert isinstance(result, bytes)
        assert result[:2] == b'\xff\xd8'  # JPEG magic bytes

    def test_composite_empty_strokes_returns_bytes(self, tmp_path):
        from app.pdf import _composite_annotations
        img_path = str(tmp_path / 'test.jpg')
        with open(img_path, 'wb') as f:
            f.write(_TINY_JPEG)
        ann = json.dumps({'version': 1, 'strokes': []})
        result = _composite_annotations(img_path, ann)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_composite_with_pen_stroke(self, tmp_path):
        from app.pdf import _composite_annotations
        img_path = str(tmp_path / 'test.jpg')
        with open(img_path, 'wb') as f:
            f.write(_TINY_JPEG)
        ann = json.dumps({
            'version': 1,
            'strokes': [{
                'tool': 'pen', 'color': '#ff0000', 'width': 0.01,
                'opacity': 1.0,
                'points': [{'x': 0.1, 'y': 0.1}, {'x': 0.9, 'y': 0.9}],
            }],
        })
        result = _composite_annotations(img_path, ann)
        assert isinstance(result, bytes)
        assert result[:2] == b'\xff\xd8'  # JPEG magic bytes

    def test_composite_all_stroke_types(self, tmp_path):
        from app.pdf import _composite_annotations
        img_path = str(tmp_path / 'test.jpg')
        with open(img_path, 'wb') as f:
            f.write(_TINY_JPEG)
        result = _composite_annotations(img_path, json.dumps(_SAMPLE_ANNOTATION))
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_composite_invalid_annotation_returns_bytes(self, tmp_path):
        from app.pdf import _composite_annotations
        img_path = str(tmp_path / 'test.jpg')
        with open(img_path, 'wb') as f:
            f.write(_TINY_JPEG)
        # Malformed JSON — should not crash, returns empty bytes or None
        result = _composite_annotations(img_path, 'not valid json {{{')
        # Either bytes (falls back to plain image) or None — must not raise
        assert result is None or isinstance(result, bytes)


# ---------------------------------------------------------------------------
# Trashed note — still exportable (export is read-only)
# ---------------------------------------------------------------------------

class TestPdfExportTrashedNote:
    def test_trashed_note_can_be_exported(self, auth_client):
        note = _note(auth_client, title='Trash Me')
        note_id = note['id']
        # Move to trash
        auth_client.delete(f'/api/notes/{note_id}')
        # Should still export (export doesn't check trash state)
        r = auth_client.get(f'/api/notes/{note_id}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'
