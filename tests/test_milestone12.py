"""Tests for body_after field: text-after-images support and editor layout fixes."""
import os
import tempfile

import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-milestone12-xyz')


@pytest.fixture()
def app(tmp_path):
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    media_path = str(tmp_path / 'uploads')

    os.environ['SECRET_KEY'] = 'test-secret-key-milestone12-xyz'
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


def _note(auth_client, title='Test', body='', body_after=''):
    return auth_client.post(
        '/api/notes', json={'title': title, 'body': body, 'body_after': body_after}
    ).get_json()


class TestBodyAfterField:
    """Verify that body_after is saved and returned correctly."""

    def test_create_note_with_body_after(self, auth_client):
        note = _note(auth_client, body='before', body_after='after images')
        assert note['body'] == 'before'
        assert note['body_after'] == 'after images'

    def test_create_note_body_after_defaults_to_empty(self, auth_client):
        note = auth_client.post('/api/notes', json={'title': 'T', 'body': 'hello'}).get_json()
        assert note['body_after'] == ''

    def test_body_after_persisted_on_update(self, auth_client):
        note = _note(auth_client, body='intro')
        note_id = note['id']
        updated = auth_client.put(
            f'/api/notes/{note_id}',
            json={'title': 'T', 'body': 'intro', 'body_after': 'conclusion'},
        ).get_json()
        assert updated['body_after'] == 'conclusion'

    def test_get_note_returns_body_after(self, auth_client):
        note = _note(auth_client, body='b', body_after='extra text')
        note_id = note['id']
        fetched = auth_client.get(f'/api/notes/{note_id}').get_json()
        assert fetched['body_after'] == 'extra text'

    def test_list_notes_includes_body_after(self, auth_client):
        _note(auth_client, title='N1', body='b', body_after='epilogue')
        notes = auth_client.get('/api/notes').get_json()
        match = next(n for n in notes if n['title'] == 'N1')
        assert match['body_after'] == 'epilogue'

    def test_update_body_after_to_empty(self, auth_client):
        note = _note(auth_client, body_after='some text')
        note_id = note['id']
        updated = auth_client.put(
            f'/api/notes/{note_id}',
            json={'title': 'T', 'body': '', 'body_after': ''},
        ).get_json()
        assert updated['body_after'] == ''

    def test_body_after_too_long_returns_400(self, auth_client):
        note = _note(auth_client)
        note_id = note['id']
        resp = auth_client.put(
            f'/api/notes/{note_id}',
            json={'title': 'T', 'body': '', 'body_after': 'x' * 100_001},
        )
        assert resp.status_code == 400

    def test_bulk_sync_includes_body_after(self, auth_client):
        note = _note(auth_client, body='start')
        note_id = note['id']
        resp = auth_client.post('/api/sync', json={
            'writes': [{'id': note_id, 'title': 'T', 'body': 'start', 'body_after': 'end'}]
        })
        assert resp.status_code == 200
        result = resp.get_json()['results'][0]
        assert result['ok'] is True
        assert result['note']['body_after'] == 'end'


class TestBodyAfterVersioning:
    """Verify body_after is included in version snapshots and restore."""

    def test_version_snapshot_includes_body_after(self, auth_client, app):
        note = _note(auth_client, body='v1', body_after='after-v1')
        note_id = note['id']
        # Trigger snapshot by updating
        auth_client.put(f'/api/notes/{note_id}',
                        json={'title': 'T', 'body': 'v2', 'body_after': 'after-v2'})
        # Check versions list exists
        versions_resp = auth_client.get(f'/api/notes/{note_id}/versions')
        assert versions_resp.status_code == 200
        versions = versions_resp.get_json()
        assert len(versions) >= 1

    def test_restore_version_restores_body_after(self, auth_client):
        note = _note(auth_client, body='original', body_after='original-after')
        note_id = note['id']
        # Update to change body_after
        auth_client.put(f'/api/notes/{note_id}',
                        json={'title': 'T', 'body': 'updated', 'body_after': 'updated-after'})
        # Get the first version (original content)
        versions = auth_client.get(f'/api/notes/{note_id}/versions').get_json()
        assert len(versions) >= 1
        version_id = versions[-1]['id']  # oldest version
        # Restore that version
        restored = auth_client.post(
            f'/api/notes/{note_id}/versions/{version_id}/restore'
        ).get_json()
        assert restored['body'] == 'original'
        assert restored['body_after'] == 'original-after'


class TestBodyAfterMigration:
    """Verify that init_db automatically adds the body_after column to an existing DB."""

    def _table_columns(self, db, table_name):
        return {row[1] for row in db.execute(f'PRAGMA table_info({table_name})').fetchall()}

    def test_body_after_added_to_existing_db(self, tmp_path):
        """Simulate an existing install without body_after and verify migration applies."""
        import sqlite3

        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)

        try:
            conn = sqlite3.connect(db_path)
            conn.executescript("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    email TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    folder_id INTEGER,
                    title TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL DEFAULT '',
                    is_pinned INTEGER NOT NULL DEFAULT 0,
                    is_archived INTEGER NOT NULL DEFAULT 0,
                    is_trashed INTEGER NOT NULL DEFAULT 0,
                    conflict_of INTEGER,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE note_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL DEFAULT '',
                    saved_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE note_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    filename TEXT NOT NULL UNIQUE,
                    original_filename TEXT NOT NULL DEFAULT '',
                    mime_type TEXT NOT NULL DEFAULT 'image/jpeg',
                    file_size INTEGER NOT NULL DEFAULT 0,
                    width INTEGER NOT NULL DEFAULT 0,
                    height INTEGER NOT NULL DEFAULT 0,
                    position INTEGER NOT NULL DEFAULT 0,
                    annotation_data TEXT,
                    caption TEXT NOT NULL DEFAULT '',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                PRAGMA user_version = 7;
            """)
            assert 'body_after' not in self._table_columns(conn, 'notes')
            assert 'body_after' not in self._table_columns(conn, 'note_versions')
            conn.close()

            media_path = str(tmp_path / 'uploads')
            os.environ['SECRET_KEY'] = 'test-secret-key-migration-m12'
            os.environ['DATABASE_PATH'] = db_path
            os.environ['MEDIA_PATH'] = media_path

            from app import create_app
            application = create_app()
            application.config['TESTING'] = True
            application.config['SESSION_COOKIE_SECURE'] = False

            with application.app_context():
                from app.database import get_db, create_user
                db = get_db()
                assert 'body_after' in self._table_columns(db, 'notes'), \
                    'body_after was not added to notes by automatic migration'
                assert 'body_after' in self._table_columns(db, 'note_versions'), \
                    'body_after was not added to note_versions by automatic migration'
                version = db.execute('PRAGMA user_version').fetchone()[0]
                assert version >= 8

                create_user('carol', 'correct-horse-battery-staple')

            with application.test_client() as c:
                c.post('/login', data={'username': 'carol',
                                       'password': 'correct-horse-battery-staple'})
                note = c.post('/api/notes', json={
                    'title': 'T', 'body': 'hello', 'body_after': 'world'
                }).get_json()
                assert note['body_after'] == 'world'
        finally:
            os.unlink(db_path)
            os.environ.pop('MEDIA_PATH', None)
            os.environ.pop('DATABASE_PATH', None)


# ---------------------------------------------------------------------------
# Helpers for image upload
# ---------------------------------------------------------------------------
import io as _io

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


def _upload(auth_client, note_id, data=None, filename='photo.jpg', mime='image/jpeg'):
    if data is None:
        data = _TINY_JPEG
    return auth_client.post(
        f'/api/notes/{note_id}/images',
        data={'image': (_io.BytesIO(data), filename, mime)},
        content_type='multipart/form-data',
    ).get_json()


# ---------------------------------------------------------------------------
# section_text field — text between images
# ---------------------------------------------------------------------------

class TestImageSectionTextField:
    """Verify that section_text is returned by upload and list endpoints."""

    def test_upload_returns_empty_section_text(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        assert 'section_text' in img
        assert img['section_text'] == ''

    def test_list_images_returns_section_text_field(self, auth_client):
        note = _note(auth_client)
        _upload(auth_client, note['id'])
        r = auth_client.get(f'/api/notes/{note["id"]}/images')
        images = r.get_json()
        assert len(images) == 1
        assert 'section_text' in images[0]
        assert images[0]['section_text'] == ''


class TestImageSectionTextUpdate:
    """Verify that section_text can be set and retrieved."""

    def test_set_section_text(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        r = auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'section_text': 'Some text between images'},
        )
        assert r.status_code == 200
        assert r.get_json()['section_text'] == 'Some text between images'

    def test_section_text_persists_after_list(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'section_text': 'Persisted section text'},
        )
        images = auth_client.get(f'/api/notes/{note["id"]}/images').get_json()
        assert images[0]['section_text'] == 'Persisted section text'

    def test_section_text_non_string_returns_400(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        r = auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'section_text': 12345},
        )
        assert r.status_code == 400

    def test_put_with_no_fields_returns_400(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        r = auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={},
        )
        assert r.status_code == 400

    def test_section_text_multiline(self, auth_client):
        note = _note(auth_client)
        img = _upload(auth_client, note['id'])
        text = 'Line one\nLine two\nLine three'
        r = auth_client.put(
            f'/api/notes/{note["id"]}/images/{img["id"]}',
            json={'section_text': text},
        )
        assert r.status_code == 200
        assert r.get_json()['section_text'] == text


class TestSectionTextMigration:
    """Verify that init_db automatically adds the section_text column to an existing DB."""

    def _table_columns(self, db, table_name):
        return {row[1] for row in db.execute(f'PRAGMA table_info({table_name})').fetchall()}

    def test_section_text_added_to_existing_db(self, tmp_path):
        """Simulate an existing install without section_text and verify migration applies."""
        import sqlite3

        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)

        try:
            conn = sqlite3.connect(db_path)
            conn.executescript("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    email TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 1,
                    folder_id INTEGER,
                    title TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL DEFAULT '',
                    body_after TEXT NOT NULL DEFAULT '',
                    is_pinned INTEGER NOT NULL DEFAULT 0,
                    is_archived INTEGER NOT NULL DEFAULT 0,
                    is_trashed INTEGER NOT NULL DEFAULT 0,
                    conflict_of INTEGER,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE note_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL DEFAULT '',
                    body_after TEXT NOT NULL DEFAULT '',
                    saved_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE note_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    filename TEXT NOT NULL UNIQUE,
                    original_filename TEXT NOT NULL DEFAULT '',
                    mime_type TEXT NOT NULL DEFAULT 'image/jpeg',
                    file_size INTEGER NOT NULL DEFAULT 0,
                    width INTEGER NOT NULL DEFAULT 0,
                    height INTEGER NOT NULL DEFAULT 0,
                    position INTEGER NOT NULL DEFAULT 0,
                    annotation_data TEXT,
                    caption TEXT NOT NULL DEFAULT '',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                PRAGMA user_version = 8;
            """)
            # Confirm section_text is NOT present before migration
            assert 'section_text' not in self._table_columns(conn, 'note_images')
            conn.close()

            media_path = str(tmp_path / 'uploads')
            os.environ['SECRET_KEY'] = 'test-secret-key-migration-m13'
            os.environ['DATABASE_PATH'] = db_path
            os.environ['MEDIA_PATH'] = media_path

            from app import create_app
            application = create_app()
            application.config['TESTING'] = True
            application.config['SESSION_COOKIE_SECURE'] = False

            with application.app_context():
                from app.database import get_db, create_user
                db = get_db()
                assert 'section_text' in self._table_columns(db, 'note_images'), \
                    'section_text was not added to note_images by automatic migration'
                version = db.execute('PRAGMA user_version').fetchone()[0]
                assert version >= 9

                create_user('dave', 'correct-horse-battery-staple')

            with application.test_client() as c:
                c.post('/login', data={'username': 'dave',
                                       'password': 'correct-horse-battery-staple'})
                note = c.post('/api/notes', json={'title': 'T', 'body': 'hello'}).get_json()
                img = c.post(
                    f'/api/notes/{note["id"]}/images',
                    data={'image': (_io.BytesIO(_TINY_JPEG), 'test.jpg', 'image/jpeg')},
                    content_type='multipart/form-data',
                ).get_json()
                assert 'section_text' in img
                assert img['section_text'] == ''
        finally:
            os.unlink(db_path)
            os.environ.pop('MEDIA_PATH', None)
            os.environ.pop('DATABASE_PATH', None)
