"""Tests for Milestone 11: Image caption feature and PDF export format fix."""
import io
import json
import os
import tempfile

import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-milestone11-xyz')

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


def _make_webp_bytes():
    """Create minimal valid WebP image bytes using Pillow."""
    from PIL import Image as PILImage
    buf = io.BytesIO()
    PILImage.new('RGB', (10, 10), color=(255, 0, 0)).save(buf, format='WEBP')
    return buf.getvalue()


@pytest.fixture()
def app(tmp_path):
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    media_path = str(tmp_path / 'uploads')

    os.environ['SECRET_KEY'] = 'test-secret-key-milestone11-xyz'
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


def _note(auth_client, title='Test', body=''):
    return auth_client.post('/api/notes', json={'title': title, 'body': body}).get_json()


def _upload(auth_client, note_id, data=None, filename='photo.jpg', mime='image/jpeg'):
    if data is None:
        data = _TINY_JPEG
    return auth_client.post(
        f'/api/notes/{note_id}/images',
        data={'image': (io.BytesIO(data), filename, mime)},
        content_type='multipart/form-data',
    ).get_json()


# ---------------------------------------------------------------------------
# Caption field — returned by image list and upload
# ---------------------------------------------------------------------------

class TestImageCaptionField:
    def test_upload_returns_empty_caption(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        assert 'caption' in img
        assert img['caption'] == ''

    def test_list_images_returns_caption_field(self, auth_client):
        note = _note(auth_client)
        _upload(auth_client, note['id'])
        r = auth_client.get(f'/api/notes/{note["id"]}/images')
        images = r.get_json()
        assert len(images) == 1
        assert 'caption' in images[0]
        assert images[0]['caption'] == ''


# ---------------------------------------------------------------------------
# Caption update via PUT endpoint
# ---------------------------------------------------------------------------

class TestImageCaptionUpdate:
    def test_set_caption(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        r = auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'caption': 'My caption text'},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data['caption'] == 'My caption text'

    def test_caption_persists_after_list(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'caption': 'Persisted caption'},
        )
        images = auth_client.get(f'/api/notes/{note["id"]}/images').get_json()
        assert images[0]['caption'] == 'Persisted caption'

    def test_update_caption_and_annotation_together(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        r = auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'caption': 'both fields', 'annotation_data': None},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data['caption'] == 'both fields'

    def test_caption_only_update_requires_no_annotation_data(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        r = auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'caption': 'caption only'},
        )
        assert r.status_code == 200

    def test_put_with_neither_field_returns_400(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        r = auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'irrelevant': 'field'},
        )
        assert r.status_code == 400

    def test_caption_non_string_returns_400(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        r = auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'caption': 12345},
        )
        assert r.status_code == 400

    def test_caption_length_limit(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        long_caption = 'x' * 3000
        r = auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'caption': long_caption},
        )
        assert r.status_code == 200
        # Stored value should be truncated to at most 2000 chars
        assert len(r.get_json()['caption']) <= 2000

    def test_update_caption_wrong_note_returns_404(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        r = auth_client.put(
            f'/api/notes/99999/images/{img["id"]}',
            json={'caption': 'bad'},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# PDF export with caption
# ---------------------------------------------------------------------------

class TestPdfExportWithCaption:
    def test_pdf_export_with_captioned_image(self, auth_client):
        note = _note(auth_client, title='Caption Test', body='')
        img = _upload(auth_client, note['id'])
        auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'caption': 'My test caption'},
        )
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'

    def test_pdf_export_image_without_caption_uses_filename(self, auth_client):
        note = _note(auth_client, title='Filename Test', body='')
        _upload(auth_client, note['id'])
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'


# ---------------------------------------------------------------------------
# PDF export — WebP image format compatibility fix
# ---------------------------------------------------------------------------

class TestPdfExportWebPFix:
    def test_pdf_export_with_webp_image_succeeds(self, auth_client):
        """A WebP image without annotations must not cause a 500 error."""
        try:
            webp_bytes = _make_webp_bytes()
        except Exception:
            pytest.skip('Pillow WebP support not available')

        note = _note(auth_client, title='WebP Test', body='')
        _upload(auth_client, note['id'], data=webp_bytes,
                filename='photo.webp', mime='image/webp')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'
