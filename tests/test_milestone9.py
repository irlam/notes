"""Tests for Milestone 9: Version history and conflict copy management."""
import os
import tempfile
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-milestone9-xyz123')


@pytest.fixture()
def app(tmp_path):
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    media_path = str(tmp_path / 'uploads')

    os.environ['SECRET_KEY'] = 'test-secret-key-milestone9-xyz123'
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


def make_note(auth_client, title='Test', body='Body'):
    r = auth_client.post('/api/notes', json={'title': title, 'body': body})
    assert r.status_code == 201
    return r.get_json()


# ---------------------------------------------------------------------------
# Version history
# ---------------------------------------------------------------------------

class TestVersionHistory:
    def test_list_versions_empty_initially(self, auth_client):
        note = make_note(auth_client)
        r = auth_client.get(f'/api/notes/{note["id"]}/versions')
        assert r.status_code == 200
        assert r.get_json() == []

    def test_version_created_on_update(self, auth_client):
        note = make_note(auth_client, title='Original', body='First body')
        auth_client.put(f'/api/notes/{note["id"]}',
                        json={'title': 'Updated', 'body': 'Second body'})
        r = auth_client.get(f'/api/notes/{note["id"]}/versions')
        assert r.status_code == 200
        versions = r.get_json()
        assert len(versions) == 1
        assert versions[0]['title'] == 'Original'

    def test_multiple_versions_ordered_newest_first(self, auth_client):
        note = make_note(auth_client, title='v1', body='body1')
        auth_client.put(f'/api/notes/{note["id"]}', json={'title': 'v2', 'body': 'body2'})
        auth_client.put(f'/api/notes/{note["id"]}', json={'title': 'v3', 'body': 'body3'})
        r = auth_client.get(f'/api/notes/{note["id"]}/versions')
        versions = r.get_json()
        assert len(versions) == 2
        # Newest first
        assert versions[0]['title'] == 'v2'
        assert versions[1]['title'] == 'v1'

    def test_versions_require_auth(self, client):
        r = client.get('/api/notes/1/versions')
        assert r.status_code in (401, 302)

    def test_versions_404_for_unowned_note(self, auth_client, app, tmp_path):
        """Cannot list versions for another user's note."""
        db_fd2, db_path2 = tempfile.mkstemp(suffix='.db')
        os.close(db_fd2)
        os.environ['DATABASE_PATH'] = db_path2
        from app import create_app
        app2 = create_app()
        app2.config['TESTING'] = True
        app2.config['SESSION_COOKIE_SECURE'] = False
        with app2.app_context():
            from app.database import create_user
            create_user('bob', 'correct-horse-battery')
        client2 = app2.test_client()
        client2.post('/login', data={'username': 'bob', 'password': 'correct-horse-battery'})
        note = make_note(auth_client)
        r = client2.get(f'/api/notes/{note["id"]}/versions')
        assert r.status_code == 404
        os.unlink(db_path2)

    def test_restore_version(self, auth_client):
        note = make_note(auth_client, title='Original', body='Original body')
        auth_client.put(f'/api/notes/{note["id"]}',
                        json={'title': 'Changed', 'body': 'Changed body'})
        # Get versions
        versions = auth_client.get(f'/api/notes/{note["id"]}/versions').get_json()
        version_id = versions[0]['id']

        r = auth_client.post(
            f'/api/notes/{note["id"]}/versions/{version_id}/restore'
        )
        assert r.status_code == 200
        restored = r.get_json()
        assert restored['title'] == 'Original'
        assert restored['body'] == 'Original body'

    def test_restore_snapshots_current_before_restoring(self, auth_client):
        """The current content should be preserved as a version before restoring."""
        note = make_note(auth_client, title='v1', body='v1 body')
        auth_client.put(f'/api/notes/{note["id"]}', json={'title': 'v2', 'body': 'v2 body'})
        versions = auth_client.get(f'/api/notes/{note["id"]}/versions').get_json()
        version_id = versions[0]['id']  # v1

        auth_client.post(f'/api/notes/{note["id"]}/versions/{version_id}/restore')

        versions_after = auth_client.get(f'/api/notes/{note["id"]}/versions').get_json()
        titles = [v['title'] for v in versions_after]
        assert 'v2' in titles  # v2 should be saved as a version before restore

    def test_restore_version_404_wrong_note(self, auth_client):
        note1 = make_note(auth_client, title='N1')
        note2 = make_note(auth_client, title='N2')
        auth_client.put(f'/api/notes/{note1["id"]}', json={'title': 'N1b', 'body': ''})
        versions = auth_client.get(f'/api/notes/{note1["id"]}/versions').get_json()
        version_id = versions[0]['id']
        r = auth_client.post(
            f'/api/notes/{note2["id"]}/versions/{version_id}/restore'
        )
        assert r.status_code == 404

    def test_restore_trashed_note_returns_404(self, auth_client):
        note = make_note(auth_client, title='T')
        auth_client.put(f'/api/notes/{note["id"]}', json={'title': 'T2', 'body': ''})
        versions = auth_client.get(f'/api/notes/{note["id"]}/versions').get_json()
        auth_client.delete(f'/api/notes/{note["id"]}')  # trash
        r = auth_client.post(
            f'/api/notes/{note["id"]}/versions/{versions[0]["id"]}/restore'
        )
        assert r.status_code == 404

    def test_version_response_includes_id_and_saved_at(self, auth_client):
        note = make_note(auth_client)
        auth_client.put(f'/api/notes/{note["id"]}', json={'title': 'v2', 'body': ''})
        versions = auth_client.get(f'/api/notes/{note["id"]}/versions').get_json()
        assert 'id' in versions[0]
        assert 'saved_at' in versions[0]
        assert 'title' in versions[0]


# ---------------------------------------------------------------------------
# Version retention / pruning
# ---------------------------------------------------------------------------

class TestVersionRetention:
    def test_max_50_versions_kept(self, auth_client):
        note = make_note(auth_client, title='t0', body='b0')
        for i in range(1, 55):
            auth_client.put(f'/api/notes/{note["id"]}',
                            json={'title': f't{i}', 'body': f'b{i}'})
        versions = auth_client.get(f'/api/notes/{note["id"]}/versions').get_json()
        assert len(versions) <= 50


# ---------------------------------------------------------------------------
# Conflict copy creation
# ---------------------------------------------------------------------------

class TestConflictCopies:
    def test_no_conflict_without_client_updated_at(self, auth_client):
        note = make_note(auth_client, title='T', body='B')
        r = auth_client.put(f'/api/notes/{note["id"]}',
                            json={'title': 'T2', 'body': 'B2'})
        assert r.status_code == 200
        d = r.get_json()
        assert 'conflict_note_id' not in d

    def test_no_conflict_when_client_updated_at_matches(self, auth_client):
        note = make_note(auth_client, title='T', body='B')
        r = auth_client.put(
            f'/api/notes/{note["id"]}',
            json={'title': 'T2', 'body': 'B2',
                  'client_updated_at': note['updated_at']}
        )
        assert r.status_code == 200
        d = r.get_json()
        assert 'conflict_note_id' not in d

    def test_conflict_created_when_timestamps_differ(self, auth_client):
        note = make_note(auth_client, title='T', body='B')
        r = auth_client.put(
            f'/api/notes/{note["id"]}',
            json={'title': 'T2', 'body': 'B2',
                  'client_updated_at': '2000-01-01 00:00:00'}
        )
        assert r.status_code == 200
        d = r.get_json()
        assert 'conflict_note_id' in d
        assert d['conflict_note_id'] is not None

    def test_conflict_copy_has_conflict_of_set(self, auth_client):
        note = make_note(auth_client, title='T', body='B')
        r = auth_client.put(
            f'/api/notes/{note["id"]}',
            json={'title': 'T2', 'body': 'B2',
                  'client_updated_at': '2000-01-01 00:00:00'}
        )
        conflict_id = r.get_json()['conflict_note_id']
        conflicts = auth_client.get('/api/conflicts').get_json()
        assert any(c['id'] == conflict_id for c in conflicts)
        conflict = next(c for c in conflicts if c['id'] == conflict_id)
        assert conflict['conflict_of'] == note['id']

    def test_conflict_copy_title_prefix(self, auth_client):
        note = make_note(auth_client, title='My Note', body='B')
        r = auth_client.put(
            f'/api/notes/{note["id"]}',
            json={'title': 'T2', 'body': 'B2',
                  'client_updated_at': '2000-01-01 00:00:00'}
        )
        conflict_id = r.get_json()['conflict_note_id']
        conflicts = auth_client.get('/api/conflicts').get_json()
        conflict = next(c for c in conflicts if c['id'] == conflict_id)
        assert conflict['title'].startswith('[Conflict Copy]')

    def test_conflict_copy_preserves_server_body(self, auth_client):
        note = make_note(auth_client, title='T', body='Server body content')
        r = auth_client.put(
            f'/api/notes/{note["id"]}',
            json={'title': 'T2', 'body': 'Client body',
                  'client_updated_at': '2000-01-01 00:00:00'}
        )
        conflict_id = r.get_json()['conflict_note_id']
        conflicts = auth_client.get('/api/conflicts').get_json()
        conflict = next(c for c in conflicts if c['id'] == conflict_id)
        assert conflict['body'] == 'Server body content'

    def test_list_conflicts_empty(self, auth_client):
        r = auth_client.get('/api/conflicts')
        assert r.status_code == 200
        assert r.get_json() == []

    def test_list_conflicts_requires_auth(self, client):
        r = client.get('/api/conflicts')
        assert r.status_code in (401, 302)

    def test_delete_conflict(self, auth_client):
        note = make_note(auth_client, title='T', body='B')
        r = auth_client.put(
            f'/api/notes/{note["id"]}',
            json={'title': 'T2', 'body': 'B2',
                  'client_updated_at': '2000-01-01 00:00:00'}
        )
        conflict_id = r.get_json()['conflict_note_id']
        dr = auth_client.delete(f'/api/conflicts/{conflict_id}')
        assert dr.status_code == 204
        conflicts = auth_client.get('/api/conflicts').get_json()
        assert not any(c['id'] == conflict_id for c in conflicts)

    def test_delete_conflict_requires_auth(self, client):
        r = client.delete('/api/conflicts/1')
        assert r.status_code in (401, 302)

    def test_delete_conflict_404_for_normal_note(self, auth_client):
        note = make_note(auth_client)
        r = auth_client.delete(f'/api/conflicts/{note["id"]}')
        assert r.status_code == 404

    def test_conflict_not_in_active_list(self, auth_client):
        note = make_note(auth_client, title='T', body='B')
        auth_client.put(
            f'/api/notes/{note["id"]}',
            json={'title': 'T2', 'body': 'B2',
                  'client_updated_at': '2000-01-01 00:00:00'}
        )
        active = auth_client.get('/api/notes?filter=active').get_json()
        assert all(n.get('conflict_of') is None for n in active)

    def test_filter_conflicts_in_notes_list(self, auth_client):
        note = make_note(auth_client, title='T', body='B')
        auth_client.put(
            f'/api/notes/{note["id"]}',
            json={'title': 'T2', 'body': 'B2',
                  'client_updated_at': '2000-01-01 00:00:00'}
        )
        conflicts_list = auth_client.get('/api/notes?filter=conflicts').get_json()
        assert len(conflicts_list) >= 1
        assert all(n['conflict_of'] is not None for n in conflicts_list)


# ---------------------------------------------------------------------------
# Note response includes conflict_of field
# ---------------------------------------------------------------------------

class TestNoteResponseFields:
    def test_note_has_conflict_of_field(self, auth_client):
        note = make_note(auth_client)
        r = auth_client.get(f'/api/notes/{note["id"]}')
        d = r.get_json()
        assert 'conflict_of' in d
        assert d['conflict_of'] is None

    def test_list_notes_have_conflict_of_field(self, auth_client):
        make_note(auth_client)
        notes = auth_client.get('/api/notes').get_json()
        for n in notes:
            assert 'conflict_of' in n
