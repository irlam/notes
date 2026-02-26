"""Tests for Milestone 6: PWA installability, offline basics, and sync queue."""
import os
import tempfile
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-abcdef1234567890')


@pytest.fixture()
def app(tmp_path):
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
    client.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
    return client


def _note(auth_client, title='Test', body='Body'):
    return auth_client.post('/api/notes', json={'title': title, 'body': body}).get_json()


# ---------------------------------------------------------------------------
# GET /sw.js — service worker served from root with correct headers
# ---------------------------------------------------------------------------

class TestServiceWorkerRoute:
    def test_sw_js_returns_200(self, client):
        resp = client.get('/sw.js')
        assert resp.status_code == 200

    def test_sw_js_content_type_is_javascript(self, client):
        resp = client.get('/sw.js')
        assert 'javascript' in resp.content_type

    def test_sw_js_has_service_worker_allowed_header(self, client):
        resp = client.get('/sw.js')
        assert resp.headers.get('Service-Worker-Allowed') == '/'

    def test_sw_js_has_no_cache_header(self, client):
        resp = client.get('/sw.js')
        cc = resp.headers.get('Cache-Control', '')
        assert 'no-cache' in cc

    def test_sw_js_contains_cache_name(self, client):
        resp = client.get('/sw.js')
        assert b'notes-v2' in resp.data

    def test_sw_js_registers_notes_list_cache(self, client):
        resp = client.get('/sw.js')
        assert b'notes-list-v2' in resp.data


# ---------------------------------------------------------------------------
# POST /api/sync — bulk offline write sync
# ---------------------------------------------------------------------------

class TestSyncEndpoint:
    def test_sync_requires_auth(self, client):
        resp = client.post('/api/sync', json={'updates': []})
        assert resp.status_code == 302  # redirect to login

    def test_sync_empty_updates(self, auth_client):
        resp = auth_client.post('/api/sync', json={'updates': []})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {'results': []}

    def test_sync_single_note(self, auth_client):
        note = _note(auth_client)
        resp = auth_client.post('/api/sync', json={
            'updates': [{'id': note['id'], 'title': 'Updated', 'body': 'New body'}]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['results']) == 1
        assert data['results'][0]['ok'] is True
        assert data['results'][0]['id'] == note['id']

    def test_sync_updates_note_content(self, auth_client):
        note = _note(auth_client)
        auth_client.post('/api/sync', json={
            'updates': [{'id': note['id'], 'title': 'Synced title', 'body': 'Synced body'}]
        })
        updated = auth_client.get(f'/api/notes/{note["id"]}').get_json()
        assert updated['title'] == 'Synced title'
        assert updated['body'] == 'Synced body'

    def test_sync_multiple_notes(self, auth_client):
        n1 = _note(auth_client, title='Note 1', body='')
        n2 = _note(auth_client, title='Note 2', body='')
        resp = auth_client.post('/api/sync', json={
            'updates': [
                {'id': n1['id'], 'title': 'Updated 1', 'body': 'B1'},
                {'id': n2['id'], 'title': 'Updated 2', 'body': 'B2'},
            ]
        })
        assert resp.status_code == 200
        results = resp.get_json()['results']
        assert len(results) == 2
        assert all(r['ok'] for r in results)

    def test_sync_skips_missing_note(self, auth_client):
        resp = auth_client.post('/api/sync', json={
            'updates': [{'id': 99999, 'title': 'X', 'body': ''}]
        })
        assert resp.status_code == 200
        results = resp.get_json()['results']
        assert len(results) == 1
        assert results[0]['ok'] is False
        assert 'not found' in results[0]['error']

    def test_sync_does_not_affect_other_users_notes(self, auth_client, app):
        """A user cannot sync another user's notes."""
        # Create a note as alice
        note = _note(auth_client)
        note_id = note['id']

        # Create bob and try to sync alice's note
        with app.app_context():
            from app.database import create_user
            create_user('bob', 'correct-horse-battery')

        bob_client = app.test_client()
        bob_client.post('/login', data={'username': 'bob', 'password': 'correct-horse-battery'})
        resp = bob_client.post('/api/sync', json={
            'updates': [{'id': note_id, 'title': 'Hacked', 'body': ''}]
        })
        assert resp.status_code == 200
        results = resp.get_json()['results']
        assert results[0]['ok'] is False

        # Verify alice's note is unchanged
        original = auth_client.get(f'/api/notes/{note_id}').get_json()
        assert original['title'] == 'Test'

    def test_sync_ignores_trashed_notes(self, auth_client):
        note = _note(auth_client)
        # Trash the note
        auth_client.delete(f'/api/notes/{note["id"]}')
        resp = auth_client.post('/api/sync', json={
            'updates': [{'id': note['id'], 'title': 'Untrashed title', 'body': ''}]
        })
        assert resp.status_code == 200
        results = resp.get_json()['results']
        assert results[0]['ok'] is False

    def test_sync_invalid_updates_type_returns_400(self, auth_client):
        resp = auth_client.post('/api/sync', json={'updates': 'not-a-list'})
        assert resp.status_code == 400

    def test_sync_invalid_note_id_returns_error_result(self, auth_client):
        resp = auth_client.post('/api/sync', json={
            'updates': [{'id': 'not-an-int', 'title': 'X', 'body': ''}]
        })
        assert resp.status_code == 200
        results = resp.get_json()['results']
        assert results[0]['ok'] is False

    def test_sync_preserves_is_pinned(self, auth_client):
        note = _note(auth_client)
        auth_client.post('/api/sync', json={
            'updates': [{'id': note['id'], 'title': 'T', 'body': '', 'is_pinned': 1}]
        })
        updated = auth_client.get(f'/api/notes/{note["id"]}').get_json()
        assert updated['is_pinned'] == 1


# ---------------------------------------------------------------------------
# PWA manifest served correctly
# ---------------------------------------------------------------------------

class TestPWAManifest:
    def test_manifest_accessible(self, client):
        resp = client.get('/static/manifest.json')
        assert resp.status_code == 200

    def test_manifest_has_icons(self, client):
        import json
        data = json.loads(client.get('/static/manifest.json').data)
        assert len(data.get('icons', [])) >= 2

    def test_manifest_has_start_url(self, client):
        import json
        data = json.loads(client.get('/static/manifest.json').data)
        assert data.get('start_url') == '/'

    def test_manifest_display_standalone(self, client):
        import json
        data = json.loads(client.get('/static/manifest.json').data)
        assert data.get('display') == 'standalone'
