"""Tests for Milestone 6: PWA installability, offline basics, and sync queue."""
import os
import tempfile
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-abcdef1234567890')


@pytest.fixture()
def app():
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)

    os.environ['SECRET_KEY'] = 'test-secret-key-abcdef1234567890'
    os.environ['DATABASE_PATH'] = db_path

    from app import create_app
    application = create_app()
    application.config['TESTING'] = True
    application.config['SESSION_COOKIE_SECURE'] = False

    with application.app_context():
        from app.database import create_user
        create_user('alice', 'correct-horse-battery')

    yield application

    os.unlink(db_path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    """A client already logged in as alice."""
    client.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
    return client


# ---------------------------------------------------------------------------
# Service Worker route
# ---------------------------------------------------------------------------

class TestServiceWorkerRoute:
    def test_sw_js_served_from_root(self, client):
        """GET /sw.js should serve the service worker file."""
        r = client.get('/sw.js')
        assert r.status_code == 200

    def test_sw_js_content_type(self, client):
        """Service worker should be served with a JS content type."""
        r = client.get('/sw.js')
        assert 'javascript' in r.content_type

    def test_sw_js_service_worker_allowed_header(self, client):
        """Service worker response should include Service-Worker-Allowed: / header."""
        r = client.get('/sw.js')
        assert r.headers.get('Service-Worker-Allowed') == '/'

    def test_sw_js_no_cache_header(self, client):
        """Service worker should be served with no-cache to ensure updates are detected."""
        r = client.get('/sw.js')
        assert 'no-cache' in r.headers.get('Cache-Control', '')

    def test_sw_js_contains_app_shell(self, client):
        """Service worker content should reference the app shell assets."""
        r = client.get('/sw.js')
        content = r.data.decode('utf-8')
        assert '/static/css/style.css' in content
        assert '/static/js/app.js' in content

    def test_sw_js_icons_are_served(self, client):
        """Icons referenced in the service worker app shell must be reachable."""
        r = client.get('/sw.js')
        content = r.data.decode('utf-8')
        assert '/static/icons/icon-192x192.png' in content
        assert '/static/icons/icon-512x512.png' in content
        assert client.get('/static/icons/icon-192x192.png').status_code == 200
        assert client.get('/static/icons/icon-512x512.png').status_code == 200

    def test_sw_js_contains_cache_name(self, client):
        """Service worker should declare a versioned cache name."""
        r = client.get('/sw.js')
        content = r.data.decode('utf-8')
        assert 'notes-v' in content


# ---------------------------------------------------------------------------
# Bulk sync endpoint
# ---------------------------------------------------------------------------

class TestBulkSync:
    def _create_note(self, auth_client, title='Test', body='Body'):
        r = auth_client.post('/api/notes', json={'title': title, 'body': body})
        assert r.status_code == 201
        return r.get_json()

    def test_sync_requires_auth(self, client):
        r = client.post('/api/sync', json={'writes': []})
        assert r.status_code == 302  # redirect to login

    def test_sync_empty_writes(self, auth_client):
        r = auth_client.post('/api/sync', json={'writes': []})
        assert r.status_code == 200
        data = r.get_json()
        assert data['results'] == []

    def test_sync_single_write(self, auth_client):
        note = self._create_note(auth_client, 'Original', 'Original body')
        r = auth_client.post('/api/sync', json={
            'writes': [{'id': note['id'], 'title': 'Updated offline', 'body': 'New body'}]
        })
        assert r.status_code == 200
        data = r.get_json()
        assert len(data['results']) == 1
        result = data['results'][0]
        assert result['ok'] is True
        assert result['id'] == note['id']
        assert result['note']['title'] == 'Updated offline'
        assert result['note']['body'] == 'New body'

    def test_sync_multiple_writes(self, auth_client):
        note1 = self._create_note(auth_client, 'Note 1', 'Body 1')
        note2 = self._create_note(auth_client, 'Note 2', 'Body 2')
        r = auth_client.post('/api/sync', json={
            'writes': [
                {'id': note1['id'], 'title': 'Note 1 updated', 'body': 'Body 1 updated'},
                {'id': note2['id'], 'title': 'Note 2 updated', 'body': 'Body 2 updated'},
            ]
        })
        assert r.status_code == 200
        data = r.get_json()
        assert len(data['results']) == 2
        assert all(r['ok'] for r in data['results'])

    def test_sync_nonexistent_note_returns_not_ok(self, auth_client):
        r = auth_client.post('/api/sync', json={
            'writes': [{'id': 99999, 'title': 'Ghost', 'body': ''}]
        })
        assert r.status_code == 200
        data = r.get_json()
        assert len(data['results']) == 1
        assert data['results'][0]['ok'] is False
        assert data['results'][0]['note'] is None

    def test_sync_preserves_is_pinned(self, auth_client):
        note = self._create_note(auth_client)
        r = auth_client.post('/api/sync', json={
            'writes': [{'id': note['id'], 'title': 'Pinned', 'body': '', 'is_pinned': 1}]
        })
        assert r.status_code == 200
        result = r.get_json()['results'][0]
        assert result['ok'] is True
        assert result['note']['is_pinned'] == 1

    def test_sync_skips_trashed_notes(self, auth_client):
        """Trashed notes should not be updated via sync."""
        note = self._create_note(auth_client)
        auth_client.delete(f'/api/notes/{note["id"]}')  # move to trash
        r = auth_client.post('/api/sync', json={
            'writes': [{'id': note['id'], 'title': 'Should not update', 'body': ''}]
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data['results'][0]['ok'] is False

    def test_sync_other_users_note_returns_not_ok(self, app):
        """A user cannot sync another user's note."""
        with app.app_context():
            from app.database import create_user
            create_user('bob', 'password-for-bob')

        client = app.test_client()
        # Log in as alice and create a note
        client.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
        r = client.post('/api/notes', json={'title': 'Alice note', 'body': ''})
        alice_note_id = r.get_json()['id']
        client.post('/logout')

        # Log in as bob and try to sync alice's note
        client.post('/login', data={'username': 'bob', 'password': 'password-for-bob'})
        r = client.post('/api/sync', json={
            'writes': [{'id': alice_note_id, 'title': 'Stolen', 'body': ''}]
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data['results'][0]['ok'] is False

    def test_sync_invalid_writes_type(self, auth_client):
        r = auth_client.post('/api/sync', json={'writes': 'not-a-list'})
        assert r.status_code == 400

    def test_sync_invalid_note_id_returns_not_ok(self, auth_client):
        r = auth_client.post('/api/sync', json={
            'writes': [{'id': 'bad-id', 'title': 'x', 'body': ''}]
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data['results'][0]['ok'] is False

    def test_sync_response_includes_tags(self, auth_client):
        """Sync response note objects should include the tags field."""
        note = self._create_note(auth_client)
        r = auth_client.post('/api/sync', json={
            'writes': [{'id': note['id'], 'title': 'Tagged', 'body': ''}]
        })
        assert r.status_code == 200
        result = r.get_json()['results'][0]
        assert 'tags' in result['note']

    def test_sync_no_body_defaults_empty(self, auth_client):
        """Sync endpoint handles missing writes key gracefully."""
        r = auth_client.post('/api/sync', json={})
        assert r.status_code == 200
        assert r.get_json()['results'] == []


# ---------------------------------------------------------------------------
# PWA manifest
# ---------------------------------------------------------------------------

class TestPWAManifest:
    def test_manifest_served(self, client):
        r = client.get('/static/manifest.json')
        assert r.status_code == 200

    def test_manifest_is_json(self, client):
        r = client.get('/static/manifest.json')
        data = r.get_json()
        assert data is not None

    def test_manifest_has_required_fields(self, client):
        r = client.get('/static/manifest.json')
        data = r.get_json()
        assert 'name' in data
        assert 'short_name' in data
        assert 'start_url' in data
        assert 'display' in data
        assert 'icons' in data

    def test_manifest_has_icons(self, client):
        r = client.get('/static/manifest.json')
        data = r.get_json()
        assert len(data['icons']) >= 2
        sizes = {i['sizes'] for i in data['icons']}
        assert '192x192' in sizes
        assert '512x512' in sizes

    def test_manifest_standalone_display(self, client):
        r = client.get('/static/manifest.json')
        data = r.get_json()
        assert data['display'] == 'standalone'

    def test_icons_are_served(self, client):
        r192 = client.get('/static/icons/android-chrome-192x192.png')
        r512 = client.get('/static/icons/android-chrome-512x512.png')
        assert r192.status_code == 200
        assert r512.status_code == 200
