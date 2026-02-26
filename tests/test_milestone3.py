"""Tests for Milestone 3: Folders, Tags, Search, Sort/Filter."""
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
# Folder CRUD
# ---------------------------------------------------------------------------

class TestFolderCRUD:
    def test_list_folders_empty(self, auth_client):
        resp = auth_client.get('/api/folders')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_folder(self, auth_client):
        resp = auth_client.post('/api/folders', json={'name': 'Work'})
        assert resp.status_code == 201
        f = resp.get_json()
        assert f['name'] == 'Work'
        assert 'id' in f
        assert 'created_at' in f

    def test_list_folders_returns_created(self, auth_client):
        auth_client.post('/api/folders', json={'name': 'Personal'})
        auth_client.post('/api/folders', json={'name': 'Work'})
        folders = auth_client.get('/api/folders').get_json()
        names = [f['name'] for f in folders]
        assert 'Personal' in names
        assert 'Work' in names

    def test_folders_sorted_by_name(self, auth_client):
        auth_client.post('/api/folders', json={'name': 'Zebra'})
        auth_client.post('/api/folders', json={'name': 'Alpha'})
        folders = auth_client.get('/api/folders').get_json()
        assert folders[0]['name'] == 'Alpha'
        assert folders[1]['name'] == 'Zebra'

    def test_create_folder_empty_name_returns_400(self, auth_client):
        resp = auth_client.post('/api/folders', json={'name': ''})
        assert resp.status_code == 400

    def test_create_folder_duplicate_name_returns_400(self, auth_client):
        auth_client.post('/api/folders', json={'name': 'Work'})
        resp = auth_client.post('/api/folders', json={'name': 'Work'})
        assert resp.status_code == 400

    def test_rename_folder(self, auth_client):
        fid = auth_client.post('/api/folders', json={'name': 'Old'}).get_json()['id']
        resp = auth_client.put(f'/api/folders/{fid}', json={'name': 'New'})
        assert resp.status_code == 200
        assert resp.get_json()['name'] == 'New'

    def test_rename_missing_folder_returns_404(self, auth_client):
        resp = auth_client.put('/api/folders/99999', json={'name': 'X'})
        assert resp.status_code == 404

    def test_delete_folder(self, auth_client):
        fid = auth_client.post('/api/folders', json={'name': 'Temp'}).get_json()['id']
        resp = auth_client.delete(f'/api/folders/{fid}')
        assert resp.status_code == 204
        folders = auth_client.get('/api/folders').get_json()
        assert not any(f['id'] == fid for f in folders)

    def test_delete_folder_unfiles_notes(self, auth_client):
        fid = auth_client.post('/api/folders', json={'name': 'Work'}).get_json()['id']
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': '', 'folder_id': fid}).get_json()['id']
        auth_client.delete(f'/api/folders/{fid}')
        note = auth_client.get(f'/api/notes/{nid}').get_json()
        assert note['folder_id'] is None

    def test_delete_missing_folder_returns_404(self, auth_client):
        resp = auth_client.delete('/api/folders/99999')
        assert resp.status_code == 404

    def test_folder_requires_auth(self, client):
        resp = client.get('/api/folders')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Note folder assignment
# ---------------------------------------------------------------------------

class TestNoteFolderAssignment:
    def test_create_note_with_folder(self, auth_client):
        fid = auth_client.post('/api/folders', json={'name': 'Work'}).get_json()['id']
        note = auth_client.post('/api/notes', json={'title': 'T', 'body': '', 'folder_id': fid}).get_json()
        assert note['folder_id'] == fid

    def test_create_note_without_folder(self, auth_client):
        note = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()
        assert note['folder_id'] is None

    def test_update_note_folder(self, auth_client):
        fid = auth_client.post('/api/folders', json={'name': 'Work'}).get_json()['id']
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.put(f'/api/notes/{nid}', json={'title': 'T', 'body': '', 'folder_id': fid})
        assert resp.get_json()['folder_id'] == fid

    def test_update_note_unfile(self, auth_client):
        fid = auth_client.post('/api/folders', json={'name': 'Work'}).get_json()['id']
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': '', 'folder_id': fid}).get_json()['id']
        resp = auth_client.put(f'/api/notes/{nid}', json={'title': 'T', 'body': '', 'folder_id': None})
        assert resp.get_json()['folder_id'] is None

    def test_update_note_without_folder_key_preserves_folder(self, auth_client):
        fid = auth_client.post('/api/folders', json={'name': 'Work'}).get_json()['id']
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': '', 'folder_id': fid}).get_json()['id']
        # PUT without folder_id key should preserve current folder
        resp = auth_client.put(f'/api/notes/{nid}', json={'title': 'Updated', 'body': ''})
        assert resp.get_json()['folder_id'] == fid

    def test_filter_notes_by_folder(self, auth_client):
        fid = auth_client.post('/api/folders', json={'name': 'Work'}).get_json()['id']
        nid_in = auth_client.post('/api/notes', json={'title': 'In folder', 'body': '', 'folder_id': fid}).get_json()['id']
        nid_out = auth_client.post('/api/notes', json={'title': 'No folder', 'body': ''}).get_json()['id']
        notes = auth_client.get(f'/api/notes?folder_id={fid}').get_json()
        ids = [n['id'] for n in notes]
        assert nid_in in ids
        assert nid_out not in ids

    def test_create_note_invalid_folder_returns_400(self, auth_client):
        resp = auth_client.post('/api/notes', json={'title': 'T', 'body': '', 'folder_id': 99999})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tag CRUD
# ---------------------------------------------------------------------------

class TestTagCRUD:
    def test_list_tags_empty(self, auth_client):
        resp = auth_client.get('/api/tags')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_tag(self, auth_client):
        resp = auth_client.post('/api/tags', json={'name': 'python'})
        assert resp.status_code == 201
        t = resp.get_json()
        assert t['name'] == 'python'
        assert 'id' in t

    def test_list_tags_sorted_by_name(self, auth_client):
        auth_client.post('/api/tags', json={'name': 'work'})
        auth_client.post('/api/tags', json={'name': 'ideas'})
        tags = auth_client.get('/api/tags').get_json()
        assert tags[0]['name'] == 'ideas'
        assert tags[1]['name'] == 'work'

    def test_create_tag_empty_name_returns_400(self, auth_client):
        resp = auth_client.post('/api/tags', json={'name': ''})
        assert resp.status_code == 400

    def test_create_tag_duplicate_returns_400(self, auth_client):
        auth_client.post('/api/tags', json={'name': 'dupe'})
        resp = auth_client.post('/api/tags', json={'name': 'dupe'})
        assert resp.status_code == 400

    def test_rename_tag(self, auth_client):
        tid = auth_client.post('/api/tags', json={'name': 'old'}).get_json()['id']
        resp = auth_client.put(f'/api/tags/{tid}', json={'name': 'new'})
        assert resp.status_code == 200
        assert resp.get_json()['name'] == 'new'

    def test_rename_missing_tag_returns_404(self, auth_client):
        resp = auth_client.put('/api/tags/99999', json={'name': 'x'})
        assert resp.status_code == 404

    def test_delete_tag(self, auth_client):
        tid = auth_client.post('/api/tags', json={'name': 'temp'}).get_json()['id']
        resp = auth_client.delete(f'/api/tags/{tid}')
        assert resp.status_code == 204
        tags = auth_client.get('/api/tags').get_json()
        assert not any(t['id'] == tid for t in tags)

    def test_delete_missing_tag_returns_404(self, auth_client):
        resp = auth_client.delete('/api/tags/99999')
        assert resp.status_code == 404

    def test_tags_require_auth(self, client):
        assert client.get('/api/tags').status_code == 302


# ---------------------------------------------------------------------------
# Note tag assignment
# ---------------------------------------------------------------------------

class TestNoteTagAssignment:
    def test_note_has_empty_tags_by_default(self, auth_client):
        note = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()
        assert note['tags'] == []

    def test_set_note_tags(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        tid1 = auth_client.post('/api/tags', json={'name': 'work'}).get_json()['id']
        tid2 = auth_client.post('/api/tags', json={'name': 'urgent'}).get_json()['id']
        resp = auth_client.put(f'/api/notes/{nid}/tags', json={'tag_ids': [tid1, tid2]})
        assert resp.status_code == 200
        names = [t['name'] for t in resp.get_json()]
        assert 'work' in names
        assert 'urgent' in names

    def test_get_note_includes_tags(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        tid = auth_client.post('/api/tags', json={'name': 'ideas'}).get_json()['id']
        auth_client.put(f'/api/notes/{nid}/tags', json={'tag_ids': [tid]})
        note = auth_client.get(f'/api/notes/{nid}').get_json()
        assert any(t['name'] == 'ideas' for t in note['tags'])

    def test_list_notes_includes_tags(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        tid = auth_client.post('/api/tags', json={'name': 'list-tag'}).get_json()['id']
        auth_client.put(f'/api/notes/{nid}/tags', json={'tag_ids': [tid]})
        notes = auth_client.get('/api/notes').get_json()
        note = next(n for n in notes if n['id'] == nid)
        assert any(t['name'] == 'list-tag' for t in note['tags'])

    def test_set_note_tags_replaces_existing(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        tid1 = auth_client.post('/api/tags', json={'name': 'old'}).get_json()['id']
        tid2 = auth_client.post('/api/tags', json={'name': 'new'}).get_json()['id']
        auth_client.put(f'/api/notes/{nid}/tags', json={'tag_ids': [tid1]})
        auth_client.put(f'/api/notes/{nid}/tags', json={'tag_ids': [tid2]})
        note = auth_client.get(f'/api/notes/{nid}').get_json()
        names = [t['name'] for t in note['tags']]
        assert 'new' in names
        assert 'old' not in names

    def test_set_note_tags_clears_all(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        tid = auth_client.post('/api/tags', json={'name': 'remove-me'}).get_json()['id']
        auth_client.put(f'/api/notes/{nid}/tags', json={'tag_ids': [tid]})
        auth_client.put(f'/api/notes/{nid}/tags', json={'tag_ids': []})
        note = auth_client.get(f'/api/notes/{nid}').get_json()
        assert note['tags'] == []

    def test_set_note_tags_invalid_tag_id_returns_400(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        resp = auth_client.put(f'/api/notes/{nid}/tags', json={'tag_ids': [99999]})
        assert resp.status_code == 400

    def test_set_tags_on_missing_note_returns_404(self, auth_client):
        resp = auth_client.put('/api/notes/99999/tags', json={'tag_ids': []})
        assert resp.status_code == 404

    def test_delete_tag_removes_from_notes(self, auth_client):
        nid = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        tid = auth_client.post('/api/tags', json={'name': 'cascade'}).get_json()['id']
        auth_client.put(f'/api/notes/{nid}/tags', json={'tag_ids': [tid]})
        auth_client.delete(f'/api/tags/{tid}')
        note = auth_client.get(f'/api/notes/{nid}').get_json()
        assert note['tags'] == []


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_by_title(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'Meeting notes', 'body': ''})
        auth_client.post('/api/notes', json={'title': 'Shopping list', 'body': ''})
        results = auth_client.get('/api/notes?q=meeting').get_json()
        assert len(results) == 1
        assert results[0]['title'] == 'Meeting notes'

    def test_search_by_body(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'A', 'body': 'contains python code'})
        auth_client.post('/api/notes', json={'title': 'B', 'body': 'contains java code'})
        results = auth_client.get('/api/notes?q=python').get_json()
        assert len(results) == 1
        assert results[0]['title'] == 'A'

    def test_search_by_tag_name(self, auth_client):
        nid1 = auth_client.post('/api/notes', json={'title': 'Note 1', 'body': ''}).get_json()['id']
        nid2 = auth_client.post('/api/notes', json={'title': 'Note 2', 'body': ''}).get_json()['id']
        tid = auth_client.post('/api/tags', json={'name': 'important'}).get_json()['id']
        auth_client.put(f'/api/notes/{nid1}/tags', json={'tag_ids': [tid]})
        results = auth_client.get('/api/notes?q=important').get_json()
        ids = [n['id'] for n in results]
        assert nid1 in ids
        assert nid2 not in ids

    def test_search_case_insensitive(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'UPPERCASE title', 'body': ''})
        results = auth_client.get('/api/notes?q=uppercase').get_json()
        assert len(results) == 1

    def test_search_empty_query_returns_all(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'A', 'body': ''})
        auth_client.post('/api/notes', json={'title': 'B', 'body': ''})
        results = auth_client.get('/api/notes?q=').get_json()
        assert len(results) == 2

    def test_search_no_match_returns_empty(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'Hello', 'body': ''})
        results = auth_client.get('/api/notes?q=xyznotfound').get_json()
        assert results == []

    def test_search_within_archived_filter(self, auth_client):
        r = auth_client.post('/api/notes', json={'title': 'Archived secret', 'body': ''})
        nid = r.get_json()['id']
        auth_client.post(f'/api/notes/{nid}/archive')
        results = auth_client.get('/api/notes?filter=archived&q=secret').get_json()
        assert any(n['id'] == nid for n in results)

    def test_search_within_trashed_filter(self, auth_client):
        r = auth_client.post('/api/notes', json={'title': 'Trashed secret', 'body': ''})
        nid = r.get_json()['id']
        auth_client.delete(f'/api/notes/{nid}')
        results = auth_client.get('/api/notes?filter=trashed&q=secret').get_json()
        assert any(n['id'] == nid for n in results)

    def test_search_does_not_cross_filter_boundaries(self, auth_client):
        r = auth_client.post('/api/notes', json={'title': 'archived note', 'body': ''})
        nid = r.get_json()['id']
        auth_client.post(f'/api/notes/{nid}/archive')
        # Active search should not return archived note
        results = auth_client.get('/api/notes?filter=active&q=archived').get_json()
        assert not any(n['id'] == nid for n in results)

    def test_search_like_metachar_percent(self, auth_client):
        auth_client.post('/api/notes', json={'title': '100% done', 'body': ''})
        auth_client.post('/api/notes', json={'title': 'other note', 'body': ''})
        # Searching for "100%" should match only the first note, not everything
        results = auth_client.get('/api/notes?q=100%25').get_json()
        assert len(results) == 1
        assert '100%' in results[0]['title']

    def test_search_combined_with_folder_filter(self, auth_client):
        fid = auth_client.post('/api/folders', json={'name': 'Work'}).get_json()['id']
        nid1 = auth_client.post('/api/notes', json={'title': 'work report', 'body': '', 'folder_id': fid}).get_json()['id']
        nid2 = auth_client.post('/api/notes', json={'title': 'work diary', 'body': ''}).get_json()['id']
        results = auth_client.get(f'/api/notes?folder_id={fid}&q=work').get_json()
        ids = [n['id'] for n in results]
        assert nid1 in ids
        assert nid2 not in ids


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------

class TestSort:
    def test_default_sort_updated_desc(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'First', 'body': ''})
        import time; time.sleep(1)
        auth_client.post('/api/notes', json={'title': 'Second', 'body': ''})
        notes = auth_client.get('/api/notes').get_json()
        assert notes[0]['title'] == 'Second'

    def test_sort_title_asc(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'Zebra', 'body': ''})
        auth_client.post('/api/notes', json={'title': 'Apple', 'body': ''})
        auth_client.post('/api/notes', json={'title': 'Mango', 'body': ''})
        notes = auth_client.get('/api/notes?sort=title_asc').get_json()
        titles = [n['title'] for n in notes]
        assert titles == sorted(titles)

    def test_sort_created_desc(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'Old', 'body': ''})
        import time; time.sleep(1)
        auth_client.post('/api/notes', json={'title': 'New', 'body': ''})
        notes = auth_client.get('/api/notes?sort=created_desc').get_json()
        assert notes[0]['title'] == 'New'

    def test_sort_updated_desc_pinned_first(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'Recent', 'body': ''})
        r = auth_client.post('/api/notes', json={'title': 'Old pinned', 'body': ''})
        pin_id = r.get_json()['id']
        auth_client.put(f'/api/notes/{pin_id}', json={'title': 'Old pinned', 'body': '', 'is_pinned': 1})
        notes = auth_client.get('/api/notes?sort=updated_desc').get_json()
        assert notes[0]['is_pinned'] == 1

    def test_sort_param_invalid_falls_back_to_default(self, auth_client):
        auth_client.post('/api/notes', json={'title': 'T', 'body': ''})
        resp = auth_client.get('/api/notes?sort=bogus')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tag filter via tag_id param
# ---------------------------------------------------------------------------

class TestTagFilter:
    def test_filter_by_tag_id(self, auth_client):
        nid1 = auth_client.post('/api/notes', json={'title': 'Tagged', 'body': ''}).get_json()['id']
        nid2 = auth_client.post('/api/notes', json={'title': 'Untagged', 'body': ''}).get_json()['id']
        tid = auth_client.post('/api/tags', json={'name': 'mytag'}).get_json()['id']
        auth_client.put(f'/api/notes/{nid1}/tags', json={'tag_ids': [tid]})
        results = auth_client.get(f'/api/notes?tag_id={tid}').get_json()
        ids = [n['id'] for n in results]
        assert nid1 in ids
        assert nid2 not in ids


# ---------------------------------------------------------------------------
# User isolation (folders & tags)
# ---------------------------------------------------------------------------

class TestUserIsolation:
    def test_folders_isolated_between_users(self, app, auth_client, client):
        auth_client.post('/api/folders', json={'name': 'Alice folder'})
        with app.app_context():
            from app.database import create_user
            create_user('bob', 'bobpassword1')
        client.post('/logout')  # log out alice first
        client.post('/login', data={'username': 'bob', 'password': 'bobpassword1'})
        bob_folders = client.get('/api/folders').get_json()
        assert not any(f['name'] == 'Alice folder' for f in bob_folders)

    def test_tags_isolated_between_users(self, app, auth_client, client):
        auth_client.post('/api/tags', json={'name': 'alice-tag'})
        with app.app_context():
            from app.database import create_user
            create_user('bob2', 'bobpassword2')
        client.post('/logout')  # log out alice first
        client.post('/login', data={'username': 'bob2', 'password': 'bobpassword2'})
        bob_tags = client.get('/api/tags').get_json()
        assert not any(t['name'] == 'alice-tag' for t in bob_tags)

    def test_cannot_use_other_users_folder(self, app, auth_client, client):
        with app.app_context():
            from app.database import create_user
            create_user('bob3', 'bobpassword3')
        # Switch to bob, create bob's folder
        client.post('/logout')
        client.post('/login', data={'username': 'bob3', 'password': 'bobpassword3'})
        fid = client.post('/api/folders', json={'name': 'Bob folder'}).get_json()['id']
        # Switch back to alice; alice tries to create a note in Bob's folder
        client.post('/logout')
        client.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
        resp = client.post('/api/notes', json={'title': 'T', 'body': '', 'folder_id': fid})
        assert resp.status_code == 400

    def test_cannot_use_other_users_tag(self, app, auth_client, client):
        # Create alice's note while still logged in as alice
        nid = client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()['id']
        with app.app_context():
            from app.database import create_user
            create_user('bob4', 'bobpassword4')
        # Switch to bob, create bob's tag
        client.post('/logout')
        client.post('/login', data={'username': 'bob4', 'password': 'bobpassword4'})
        tid = client.post('/api/tags', json={'name': 'bob-secret-tag'}).get_json()['id']
        # Switch back to alice; alice tries to assign bob's tag to her note
        client.post('/logout')
        client.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
        resp = client.put(f'/api/notes/{nid}/tags', json={'tag_ids': [tid]})
        assert resp.status_code == 400
