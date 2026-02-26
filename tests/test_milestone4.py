"""Tests for Milestone 4: Image upload, serve, delete, reorder."""
import io
import os
import tempfile
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-abcdef1234567890')

# ---------------------------------------------------------------------------
# Minimal valid JPEG bytes (1x1 pixel)
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

# Minimal 1x1 PNG
_TINY_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00'
    b'\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N'
    b'\x00\x00\x00\x00IEND\xaeB`\x82'
)


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


def _upload(auth_client, note_id, data=None, filename='photo.jpg', content_type='image/jpeg'):
    """Helper: POST an image to the note."""
    payload = data if data is not None else _TINY_JPEG
    return auth_client.post(
        f'/api/notes/{note_id}/images',
        data={'image': (io.BytesIO(payload), filename, content_type)},
        content_type='multipart/form-data',
    )


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

class TestImageUpload:
    def test_upload_returns_201(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = _upload(auth_client, nid)
        assert resp.status_code == 201

    def test_upload_response_fields(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        img = _upload(auth_client, nid).get_json()
        assert 'id' in img
        assert 'filename' in img
        assert 'url' in img
        assert img['url'].startswith('/media/')
        assert img['original_filename'] == 'photo.jpg'
        assert img['mime_type'] in ('image/jpeg', 'image/png', 'image/gif', 'image/webp')
        assert img['position'] == 0
        assert img['annotation_data'] is None

    def test_upload_png(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = _upload(auth_client, nid, data=_TINY_PNG, filename='snap.png', content_type='image/png')
        assert resp.status_code == 201

    def test_upload_stores_file_on_disk(self, app, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        img = _upload(auth_client, nid).get_json()
        media_dir = app.config['MEDIA_PATH']
        assert os.path.isfile(os.path.join(media_dir, img['filename']))

    def test_upload_unsupported_type_returns_400(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.post(
            f'/api/notes/{nid}/images',
            data={'image': (io.BytesIO(b'<html></html>'), 'file.html', 'text/html')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400

    def test_upload_no_file_returns_400(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.post(
            f'/api/notes/{nid}/images',
            data={},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400

    def test_upload_empty_file_returns_400(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = _upload(auth_client, nid, data=b'')
        assert resp.status_code == 400

    def test_upload_to_missing_note_returns_404(self, auth_client):
        resp = _upload(auth_client, 99999)
        assert resp.status_code == 404

    def test_upload_increments_position(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        img1 = _upload(auth_client, nid).get_json()
        img2 = _upload(auth_client, nid).get_json()
        assert img1['position'] == 0
        assert img2['position'] == 1

    def test_upload_requires_auth(self, client):
        resp = client.post(
            '/api/notes/1/images',
            data={'image': (io.BytesIO(_TINY_JPEG), 'p.jpg', 'image/jpeg')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# List images
# ---------------------------------------------------------------------------

class TestListImages:
    def test_list_empty(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.get(f'/api/notes/{nid}/images')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_returns_uploaded_images(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        _upload(auth_client, nid)
        _upload(auth_client, nid)
        imgs = auth_client.get(f'/api/notes/{nid}/images').get_json()
        assert len(imgs) == 2

    def test_list_ordered_by_position(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        i1 = _upload(auth_client, nid).get_json()
        i2 = _upload(auth_client, nid).get_json()
        imgs = auth_client.get(f'/api/notes/{nid}/images').get_json()
        assert imgs[0]['id'] == i1['id']
        assert imgs[1]['id'] == i2['id']

    def test_list_missing_note_returns_404(self, auth_client):
        resp = auth_client.get('/api/notes/99999/images')
        assert resp.status_code == 404

    def test_list_requires_auth(self, client):
        assert client.get('/api/notes/1/images').status_code == 302


# ---------------------------------------------------------------------------
# Serve media
# ---------------------------------------------------------------------------

class TestServeMedia:
    def test_serve_returns_file(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        img = _upload(auth_client, nid).get_json()
        resp = auth_client.get(img['url'])
        assert resp.status_code == 200

    def test_serve_unknown_filename_returns_404(self, auth_client):
        resp = auth_client.get('/media/nonexistent.jpg')
        assert resp.status_code == 404

    def test_serve_path_traversal_blocked(self, auth_client):
        resp = auth_client.get('/media/../etc/passwd')
        assert resp.status_code in (404, 301, 308)

    def test_serve_requires_auth(self, client):
        assert client.get('/media/anything.jpg').status_code == 302

    def test_serve_other_users_image_returns_404(self, app, auth_client, client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        img = _upload(auth_client, nid).get_json()
        with app.app_context():
            from app.database import create_user
            create_user('bob', 'bobpassword1')
        client.post('/logout')
        client.post('/login', data={'username': 'bob', 'password': 'bobpassword1'})
        resp = client.get(img['url'])
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete image
# ---------------------------------------------------------------------------

class TestDeleteImage:
    def test_delete_returns_204(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        img = _upload(auth_client, nid).get_json()
        resp = auth_client.delete(f'/api/notes/{nid}/images/{img["id"]}')
        assert resp.status_code == 204

    def test_delete_removes_from_list(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        img = _upload(auth_client, nid).get_json()
        auth_client.delete(f'/api/notes/{nid}/images/{img["id"]}')
        imgs = auth_client.get(f'/api/notes/{nid}/images').get_json()
        assert not any(i['id'] == img['id'] for i in imgs)

    def test_delete_removes_file_from_disk(self, app, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        img = _upload(auth_client, nid).get_json()
        media_dir = app.config['MEDIA_PATH']
        filepath = os.path.join(media_dir, img['filename'])
        assert os.path.isfile(filepath)
        auth_client.delete(f'/api/notes/{nid}/images/{img["id"]}')
        assert not os.path.isfile(filepath)

    def test_delete_missing_image_returns_404(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.delete(f'/api/notes/{nid}/images/99999')
        assert resp.status_code == 404

    def test_delete_requires_auth(self, client):
        assert client.delete('/api/notes/1/images/1').status_code == 302

    def test_delete_cascades_when_note_deleted(self, app, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        img = _upload(auth_client, nid).get_json()
        # Trash then permanently delete the note
        auth_client.delete(f'/api/notes/{nid}')
        auth_client.delete(f'/api/notes/{nid}/permanent')
        # The image DB record should be gone (ON DELETE CASCADE)
        media_dir = app.config['MEDIA_PATH']
        # Verify DB record is gone by checking 404 on serve
        resp = auth_client.get(img['url'])
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reorder images
# ---------------------------------------------------------------------------

class TestReorderImages:
    def test_reorder_returns_new_order(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        i1 = _upload(auth_client, nid).get_json()
        i2 = _upload(auth_client, nid).get_json()
        resp = auth_client.put(
            f'/api/notes/{nid}/images/reorder',
            json={'image_ids': [i2['id'], i1['id']]},
        )
        assert resp.status_code == 200
        result = resp.get_json()
        assert result[0]['id'] == i2['id']
        assert result[1]['id'] == i1['id']

    def test_reorder_persisted(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        i1 = _upload(auth_client, nid).get_json()
        i2 = _upload(auth_client, nid).get_json()
        auth_client.put(
            f'/api/notes/{nid}/images/reorder',
            json={'image_ids': [i2['id'], i1['id']]},
        )
        imgs = auth_client.get(f'/api/notes/{nid}/images').get_json()
        assert imgs[0]['id'] == i2['id']
        assert imgs[1]['id'] == i1['id']

    def test_reorder_missing_note_returns_404(self, auth_client):
        resp = auth_client.put(
            '/api/notes/99999/images/reorder',
            json={'image_ids': []},
        )
        assert resp.status_code == 404

    def test_reorder_requires_auth(self, client):
        assert client.put(
            '/api/notes/1/images/reorder',
            json={'image_ids': []},
        ).status_code == 302

    def test_reorder_bad_body_returns_400(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.put(
            f'/api/notes/{nid}/images/reorder',
            json={'image_ids': 'not-a-list'},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------

class TestImageUserIsolation:
    def test_cannot_access_other_users_note_images(self, app, auth_client, client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        with app.app_context():
            from app.database import create_user
            create_user('bob5', 'bobpassword5')
        client.post('/logout')
        client.post('/login', data={'username': 'bob5', 'password': 'bobpassword5'})
        resp = client.get(f'/api/notes/{nid}/images')
        assert resp.status_code == 404

    def test_cannot_delete_other_users_image(self, app, auth_client, client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        img = _upload(auth_client, nid).get_json()
        with app.app_context():
            from app.database import create_user
            create_user('bob6', 'bobpassword6')
        client.post('/logout')
        client.post('/login', data={'username': 'bob6', 'password': 'bobpassword6'})
        resp = client.delete(f'/api/notes/{nid}/images/{img["id"]}')
        assert resp.status_code == 404
