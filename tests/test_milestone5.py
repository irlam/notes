"""Tests for Milestone 5: Image annotation editor (save / load annotation_data)."""
import io
import json
import os
import tempfile
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-abcdef1234567890')

# ---------------------------------------------------------------------------
# Minimal valid JPEG (reused from test_milestone4)
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


def _upload(auth_client, note_id):
    return auth_client.post(
        f'/api/notes/{note_id}/images',
        data={'image': (io.BytesIO(_TINY_JPEG), 'photo.jpg', 'image/jpeg')},
        content_type='multipart/form-data',
    )


def _note(auth_client):
    return auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()


# ---------------------------------------------------------------------------
# PUT /api/notes/<note_id>/images/<image_id> — save annotation_data
# ---------------------------------------------------------------------------

class TestSaveAnnotation:
    def test_save_annotation_returns_200(self, auth_client):
        nid = _note(auth_client)['id']
        img = _upload(auth_client, nid).get_json()
        resp = auth_client.put(
            f'/api/notes/{nid}/images/{img["id"]}',
            json={'annotation_data': json.dumps(_SAMPLE_ANNOTATION)},
        )
        assert resp.status_code == 200

    def test_save_annotation_persisted(self, auth_client):
        nid = _note(auth_client)['id']
        img = _upload(auth_client, nid).get_json()
        ann_json = json.dumps(_SAMPLE_ANNOTATION)
        auth_client.put(
            f'/api/notes/{nid}/images/{img["id"]}',
            json={'annotation_data': ann_json},
        )
        imgs = auth_client.get(f'/api/notes/{nid}/images').get_json()
        saved = next(i for i in imgs if i['id'] == img['id'])
        assert saved['annotation_data'] is not None
        data = json.loads(saved['annotation_data'])
        assert data['version'] == 1
        assert len(data['strokes']) == 3

    def test_save_annotation_returned_in_response(self, auth_client):
        nid = _note(auth_client)['id']
        img = _upload(auth_client, nid).get_json()
        ann_json = json.dumps(_SAMPLE_ANNOTATION)
        resp = auth_client.put(
            f'/api/notes/{nid}/images/{img["id"]}',
            json={'annotation_data': ann_json},
        )
        body = resp.get_json()
        assert body['annotation_data'] == ann_json

    def test_save_annotation_dict_accepted(self, auth_client):
        """annotation_data can be sent as a JSON object (dict), not just a string."""
        nid = _note(auth_client)['id']
        img = _upload(auth_client, nid).get_json()
        resp = auth_client.put(
            f'/api/notes/{nid}/images/{img["id"]}',
            json={'annotation_data': _SAMPLE_ANNOTATION},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        data = json.loads(body['annotation_data'])
        assert data['version'] == 1

    def test_clear_annotation_with_null(self, auth_client):
        nid = _note(auth_client)['id']
        img = _upload(auth_client, nid).get_json()
        # First save some annotations
        auth_client.put(
            f'/api/notes/{nid}/images/{img["id"]}',
            json={'annotation_data': json.dumps(_SAMPLE_ANNOTATION)},
        )
        # Now clear with null
        resp = auth_client.put(
            f'/api/notes/{nid}/images/{img["id"]}',
            json={'annotation_data': None},
        )
        assert resp.status_code == 200
        assert resp.get_json()['annotation_data'] is None

    def test_save_annotation_missing_field_returns_400(self, auth_client):
        nid = _note(auth_client)['id']
        img = _upload(auth_client, nid).get_json()
        resp = auth_client.put(
            f'/api/notes/{nid}/images/{img["id"]}',
            json={'foo': 'bar'},
        )
        assert resp.status_code == 400

    def test_save_annotation_invalid_json_string_returns_400(self, auth_client):
        nid = _note(auth_client)['id']
        img = _upload(auth_client, nid).get_json()
        resp = auth_client.put(
            f'/api/notes/{nid}/images/{img["id"]}',
            json={'annotation_data': 'not-valid-json{{{'},
        )
        assert resp.status_code == 400

    def test_save_annotation_invalid_type_returns_400(self, auth_client):
        nid = _note(auth_client)['id']
        img = _upload(auth_client, nid).get_json()
        resp = auth_client.put(
            f'/api/notes/{nid}/images/{img["id"]}',
            json={'annotation_data': 12345},
        )
        assert resp.status_code == 400

    def test_save_annotation_wrong_image_returns_404(self, auth_client):
        nid = _note(auth_client)['id']
        resp = auth_client.put(
            f'/api/notes/{nid}/images/99999',
            json={'annotation_data': None},
        )
        assert resp.status_code == 404

    def test_save_annotation_wrong_note_returns_404(self, auth_client):
        nid = _note(auth_client)['id']
        img = _upload(auth_client, nid).get_json()
        resp = auth_client.put(
            f'/api/notes/99999/images/{img["id"]}',
            json={'annotation_data': None},
        )
        assert resp.status_code == 404

    def test_save_annotation_requires_auth(self, client):
        resp = client.put(
            '/api/notes/1/images/1',
            json={'annotation_data': None},
        )
        assert resp.status_code == 302


class TestAnnotationUserIsolation:
    def test_cannot_save_annotation_to_other_users_image(self, app, auth_client, client):
        nid = _note(auth_client)['id']
        img = _upload(auth_client, nid).get_json()
        with app.app_context():
            from app.database import create_user
            create_user('bob7', 'bobpassword7')
        client.post('/logout')
        client.post('/login', data={'username': 'bob7', 'password': 'bobpassword7'})
        resp = client.put(
            f'/api/notes/{nid}/images/{img["id"]}',
            json={'annotation_data': None},
        )
        assert resp.status_code == 404


class TestAnnotationDataModel:
    """Verify the annotation data model is stored and returned correctly."""

    def test_all_stroke_tools_preserved(self, auth_client):
        nid = _note(auth_client)['id']
        img = _upload(auth_client, nid).get_json()
        strokes = [
            {'tool': 'pen',         'color': '#f00', 'width': 0.006, 'opacity': 1.0,
             'points': [{'x': 0.1, 'y': 0.1}]},
            {'tool': 'highlighter', 'color': '#ff0', 'width': 0.04,  'opacity': 0.4,
             'points': [{'x': 0.2, 'y': 0.2}]},
            {'tool': 'arrow',       'color': '#00f', 'width': 0.006, 'opacity': 1.0,
             'x1': 0.0, 'y1': 0.0, 'x2': 1.0, 'y2': 1.0},
            {'tool': 'rectangle',   'color': '#0f0', 'width': 0.004, 'opacity': 1.0,
             'x1': 0.1, 'y1': 0.1, 'x2': 0.5, 'y2': 0.5},
            {'tool': 'circle',      'color': '#f0f', 'width': 0.004, 'opacity': 1.0,
             'x1': 0.3, 'y1': 0.3, 'x2': 0.7, 'y2': 0.7},
            {'tool': 'text',        'color': '#000', 'width': 0.006, 'opacity': 1.0,
             'x': 0.2, 'y': 0.5, 'text': 'Hello'},
        ]
        ann = json.dumps({'version': 1, 'strokes': strokes})
        resp = auth_client.put(
            f'/api/notes/{nid}/images/{img["id"]}',
            json={'annotation_data': ann},
        )
        assert resp.status_code == 200
        saved = json.loads(resp.get_json()['annotation_data'])
        assert saved['version'] == 1
        assert len(saved['strokes']) == 6
        tools_in = [s['tool'] for s in saved['strokes']]
        assert tools_in == ['pen', 'highlighter', 'arrow', 'rectangle', 'circle', 'text']

    def test_annotation_survives_image_reload(self, auth_client):
        """Annotation should persist after save and appear in list endpoint."""
        nid = _note(auth_client)['id']
        img = _upload(auth_client, nid).get_json()
        ann = json.dumps({'version': 1, 'strokes': []})
        auth_client.put(
            f'/api/notes/{nid}/images/{img["id"]}',
            json={'annotation_data': ann},
        )
        imgs = auth_client.get(f'/api/notes/{nid}/images').get_json()
        saved = next(i for i in imgs if i['id'] == img['id'])
        assert saved['annotation_data'] == ann
