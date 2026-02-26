"""Tests for Milestone 10 stubs: email PDF and batch export placeholder endpoints."""
import os
import tempfile
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-milestone10-xyz123')


@pytest.fixture()
def app(tmp_path):
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    media_path = str(tmp_path / 'uploads')

    os.environ['SECRET_KEY'] = 'test-secret-key-milestone10-xyz123'
    os.environ['DATABASE_PATH'] = db_path
    os.environ['MEDIA_PATH'] = media_path
    # Ensure feature flag is OFF by default for most tests
    os.environ.pop('ENABLE_EMAIL_EXPORT', None)

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
def app_flag_enabled(tmp_path):
    """App instance with ENABLE_EMAIL_EXPORT=true."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    media_path = str(tmp_path / 'uploads')

    os.environ['SECRET_KEY'] = 'test-secret-key-milestone10-xyz123'
    os.environ['DATABASE_PATH'] = db_path
    os.environ['MEDIA_PATH'] = media_path
    os.environ['ENABLE_EMAIL_EXPORT'] = 'true'

    # Re-import to pick up the new env var (module-level constant in email_export.py)
    import importlib
    import app.email_export as ee_mod
    importlib.reload(ee_mod)

    from app import create_app
    application = create_app()
    # Re-register the reloaded blueprint on the existing app — simpler: just
    # patch the constant directly after creation.
    application.config['TESTING'] = True
    application.config['SESSION_COOKIE_SECURE'] = False

    with application.app_context():
        from app.database import create_user
        create_user('bob', 'correct-horse-battery')

    yield application

    os.unlink(db_path)
    os.environ.pop('MEDIA_PATH', None)
    os.environ.pop('ENABLE_EMAIL_EXPORT', None)
    # Reload module back to default
    importlib.reload(ee_mod)


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
# email-pdf stub — feature flag OFF (default)
# ---------------------------------------------------------------------------

class TestEmailPdfStubFlagOff:
    def test_requires_auth(self, client):
        r = client.post('/api/notes/1/email-pdf')
        assert r.status_code in (302, 401)

    def test_returns_403_when_flag_off(self, auth_client):
        note = make_note(auth_client)
        r = auth_client.post(f'/api/notes/{note["id"]}/email-pdf')
        assert r.status_code == 403
        data = r.get_json()
        assert data['feature'] == 'email_pdf'
        assert data['milestone'] == 10
        assert 'error' in data

    def test_returns_json_content_type(self, auth_client):
        note = make_note(auth_client)
        r = auth_client.post(f'/api/notes/{note["id"]}/email-pdf')
        assert r.content_type.startswith('application/json')


# ---------------------------------------------------------------------------
# batch-export stub — feature flag OFF (default)
# ---------------------------------------------------------------------------

class TestBatchExportStubFlagOff:
    def test_requires_auth(self, client):
        r = client.post('/api/batch-export')
        assert r.status_code in (302, 401)

    def test_returns_403_when_flag_off(self, auth_client):
        r = auth_client.post('/api/batch-export', json={'note_ids': [1]})
        assert r.status_code == 403
        data = r.get_json()
        assert data['feature'] == 'batch_export'
        assert data['milestone'] == 10
        assert 'error' in data

    def test_returns_json_content_type(self, auth_client):
        r = auth_client.post('/api/batch-export', json={'note_ids': []})
        assert r.content_type.startswith('application/json')


# ---------------------------------------------------------------------------
# email-pdf stub — feature flag ON (returns 501)
# ---------------------------------------------------------------------------

class TestEmailPdfStubFlagOn:
    def test_returns_501_when_flag_on(self, app_flag_enabled):
        """When ENABLE_EMAIL_EXPORT=true the stub returns 501 Not Implemented."""
        import app.email_export as ee_mod
        original = ee_mod._FEATURE_ENABLED
        ee_mod._FEATURE_ENABLED = True
        try:
            with app_flag_enabled.test_client() as c:
                c.post('/login', data={'username': 'bob', 'password': 'correct-horse-battery'})
                # Create a note
                r = c.post('/api/notes', json={'title': 'T', 'body': 'B'})
                note_id = r.get_json()['id']
                r2 = c.post(f'/api/notes/{note_id}/email-pdf')
                assert r2.status_code == 501
                data = r2.get_json()
                assert data['feature'] == 'email_pdf'
                assert data['milestone'] == 10
        finally:
            ee_mod._FEATURE_ENABLED = original


class TestBatchExportStubFlagOn:
    def test_returns_501_when_flag_on(self, app_flag_enabled):
        """When ENABLE_EMAIL_EXPORT=true the stub returns 501 Not Implemented."""
        import app.email_export as ee_mod
        original = ee_mod._FEATURE_ENABLED
        ee_mod._FEATURE_ENABLED = True
        try:
            with app_flag_enabled.test_client() as c:
                c.post('/login', data={'username': 'bob', 'password': 'correct-horse-battery'})
                r = c.post('/api/batch-export', json={'note_ids': [1]})
                assert r.status_code == 501
                data = r.get_json()
                assert data['feature'] == 'batch_export'
                assert data['milestone'] == 10
        finally:
            ee_mod._FEATURE_ENABLED = original
