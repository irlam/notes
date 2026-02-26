"""Tests for Notes CRUD, autosave, pin, archive, trash/restore (Milestone 2)."""
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
# Notes list
# ---------------------------------------------------------------------------

class TestNotesList:
    def test_list_empty(self, auth_client):
        resp = auth_client.get('/api/notes')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_active_by_default(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'A', 'body': ''})
        resp = auth_client.get('/api/notes')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]['title'] == 'A'

    def test_list_returns_new_status_fields(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'T', 'body': 'B'})
        note = auth_client.get('/api/notes').get_json()[0]
        assert 'is_pinned' in note
        assert 'is_archived' in note
        assert 'is_trashed' in note
        assert note['is_pinned'] == 0
        assert note['is_archived'] == 0
        assert note['is_trashed'] == 0

    def test_filter_active_excludes_archived(self, auth_client):
        r = auth_client.post('/api/notes', json={'title': 'Keep', 'body': ''})
        note_id = r.get_json()['id']
        auth_client.post('/api/notes', json={'title': 'Archive me', 'body': ''})
        archive_id = auth_client.get('/api/notes').get_json()[0]['id']
        auth_client.post(f'/api/notes/{archive_id}/archive')

        active = auth_client.get('/api/notes?filter=active').get_json()
        ids = [n['id'] for n in active]
        assert archive_id not in ids

    def test_filter_archived_returns_archived(self, auth_client):
        r = auth_client.post('/api/notes', json={'title': 'Will archive', 'body': ''})
        note_id = r.get_json()['id']
        auth_client.post(f'/api/notes/{note_id}/archive')

        archived = auth_client.get('/api/notes?filter=archived').get_json()
        assert any(n['id'] == note_id for n in archived)

    def test_filter_trashed_returns_trashed(self, auth_client):
        r = auth_client.post('/api/notes', json={'title': 'Trash me', 'body': ''})
        note_id = r.get_json()['id']
        auth_client.delete(f'/api/notes/{note_id}')

        trashed = auth_client.get('/api/notes?filter=trashed').get_json()
        assert any(n['id'] == note_id for n in trashed)

    def test_pinned_notes_sort_first(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'Normal', 'body': ''})
        r2 = auth_client.post('/api/notes', json={'title': 'Will be pinned', 'body': ''})
        pin_id = r2.get_json()['id']
        # Pin it
        auth_client.put(f'/api/notes/{pin_id}', json={'title': 'Pinned', 'body': '', 'is_pinned': 1})

        notes = auth_client.get('/api/notes').get_json()
        assert notes[0]['id'] == pin_id
        assert notes[0]['is_pinned'] == 1


# ---------------------------------------------------------------------------
# Create note
# ---------------------------------------------------------------------------

class TestCreateNote:
    def test_create_returns_201(self, auth_client):
        resp = auth_client.post('/api/notes', json={'title': 'Hello', 'body': 'World'})
        assert resp.status_code == 201

    def test_create_returns_note_fields(self, auth_client):
        resp = auth_client.post('/api/notes', json={'title': 'T', 'body': 'B'})
        note = resp.get_json()
        assert note['title'] == 'T'
        assert note['body'] == 'B'
        assert 'id' in note
        assert 'created_at' in note
        assert 'updated_at' in note

    def test_create_empty_note(self, auth_client):
        resp = auth_client.post('/api/notes', json={})
        assert resp.status_code == 201
        note = resp.get_json()
        assert note['title'] == ''
        assert note['body'] == ''

    def test_create_requires_auth(self, client):
        resp = client.post('/api/notes', json={'title': 'x', 'body': 'y'})
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Get note
# ---------------------------------------------------------------------------

class TestGetNote:
    def test_get_existing_note(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'X', 'body': 'Y'}).get_json()['id']
        resp = auth_client.get(f'/api/notes/{note_id}')
        assert resp.status_code == 200
        assert resp.get_json()['title'] == 'X'

    def test_get_missing_note_returns_404(self, auth_client):
        resp = auth_client.get('/api/notes/99999')
        assert resp.status_code == 404

    def test_get_other_users_note_returns_404(self, app, auth_client, client):
        note_id = auth_client.post('/api/notes', json={'title': 'Secret', 'body': ''}).get_json()['id']
        with app.app_context():
            from app.database import create_user
            create_user('bob', 'bobpassword1')
        client.post('/logout')  # log out alice first
        client.post('/login', data={'username': 'bob', 'password': 'bobpassword1'})
        resp = client.get(f'/api/notes/{note_id}')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update note
# ---------------------------------------------------------------------------

class TestUpdateNote:
    def test_update_title_and_body(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'Old', 'body': 'Old'}).get_json()['id']
        resp = auth_client.put(f'/api/notes/{note_id}', json={'title': 'New', 'body': 'New'})
        assert resp.status_code == 200
        updated = resp.get_json()
        assert updated['title'] == 'New'
        assert updated['body'] == 'New'

    def test_update_bumps_updated_at(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'A', 'body': ''}).get_json()['id']
        before = auth_client.get(f'/api/notes/{note_id}').get_json()['updated_at']
        import time; time.sleep(1)
        auth_client.put(f'/api/notes/{note_id}', json={'title': 'B', 'body': ''})
        after = auth_client.get(f'/api/notes/{note_id}').get_json()['updated_at']
        assert after >= before

    def test_update_sets_is_pinned(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.put(f'/api/notes/{note_id}', json={'title': 'T', 'body': '', 'is_pinned': 1})
        assert resp.get_json()['is_pinned'] == 1

    def test_update_missing_note_returns_404(self, auth_client):
        resp = auth_client.put('/api/notes/99999', json={'title': '', 'body': ''})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Pin note
# ---------------------------------------------------------------------------

class TestPinNote:
    def test_pin_note_via_put(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.put(f'/api/notes/{note_id}', json={'title': 'T', 'body': '', 'is_pinned': 1})
        assert resp.get_json()['is_pinned'] == 1

    def test_unpin_note_via_put(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        auth_client.put(f'/api/notes/{note_id}', json={'title': 'T', 'body': '', 'is_pinned': 1})
        resp = auth_client.put(f'/api/notes/{note_id}', json={'title': 'T', 'body': '', 'is_pinned': 0})
        assert resp.get_json()['is_pinned'] == 0


# ---------------------------------------------------------------------------
# Archive / unarchive
# ---------------------------------------------------------------------------

class TestArchive:
    def test_archive_note(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.post(f'/api/notes/{note_id}/archive')
        assert resp.status_code == 200
        assert resp.get_json()['is_archived'] == 1

    def test_unarchive_note_toggles(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        auth_client.post(f'/api/notes/{note_id}/archive')  # archive
        resp = auth_client.post(f'/api/notes/{note_id}/archive')  # unarchive
        assert resp.get_json()['is_archived'] == 0

    def test_archive_removes_from_active(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        auth_client.post(f'/api/notes/{note_id}/archive')
        active = auth_client.get('/api/notes?filter=active').get_json()
        assert not any(n['id'] == note_id for n in active)

    def test_archive_trashed_note_returns_404(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        auth_client.delete(f'/api/notes/{note_id}')  # move to trash
        resp = auth_client.post(f'/api/notes/{note_id}/archive')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Trash / restore
# ---------------------------------------------------------------------------

class TestTrash:
    def test_delete_moves_to_trash(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.delete(f'/api/notes/{note_id}')
        assert resp.status_code == 204
        # Still exists in trash
        trashed = auth_client.get('/api/notes?filter=trashed').get_json()
        assert any(n['id'] == note_id for n in trashed)
        # Not in active
        active = auth_client.get('/api/notes?filter=active').get_json()
        assert not any(n['id'] == note_id for n in active)

    def test_restore_from_trash(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        auth_client.delete(f'/api/notes/{note_id}')
        resp = auth_client.post(f'/api/notes/{note_id}/restore')
        assert resp.status_code == 200
        assert resp.get_json()['is_trashed'] == 0
        # Visible in active again
        active = auth_client.get('/api/notes?filter=active').get_json()
        assert any(n['id'] == note_id for n in active)

    def test_restore_non_trashed_returns_404(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.post(f'/api/notes/{note_id}/restore')
        assert resp.status_code == 404

    def test_permanent_delete_from_trash(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        auth_client.delete(f'/api/notes/{note_id}')
        resp = auth_client.delete(f'/api/notes/{note_id}/permanent')
        assert resp.status_code == 204
        # Gone from trash
        trashed = auth_client.get('/api/notes?filter=trashed').get_json()
        assert not any(n['id'] == note_id for n in trashed)
        # get 404
        assert auth_client.get(f'/api/notes/{note_id}').status_code == 404

    def test_permanent_delete_non_trashed_returns_404(self, auth_client):
        note_id = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.delete(f'/api/notes/{note_id}/permanent')
        assert resp.status_code == 404

    def test_trash_missing_note_returns_404(self, auth_client):
        resp = auth_client.delete('/api/notes/99999')
        assert resp.status_code == 404
