"""Tests for Milestone 10: Email PDF and Batch Export (full implementation)."""
import io
import os
import smtplib
import tempfile
import zipfile
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-milestone10-impl')


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app(tmp_path):
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    media_path = str(tmp_path / 'uploads')

    os.environ['SECRET_KEY'] = 'test-secret-key-milestone10-impl'
    os.environ['DATABASE_PATH'] = db_path
    os.environ['MEDIA_PATH'] = media_path
    os.environ.pop('ENABLE_EMAIL_EXPORT', None)

    from app import create_app
    application = create_app()
    application.config['TESTING'] = True
    application.config['SESSION_COOKIE_SECURE'] = False

    with application.app_context():
        from app.database import create_user
        create_user('alice', 'correct-horse-battery')
        create_user('bob', 'correct-horse-battery')

    yield application

    os.unlink(db_path)
    os.environ.pop('MEDIA_PATH', None)


@pytest.fixture()
def app_enabled(tmp_path):
    """App with ENABLE_EMAIL_EXPORT=true."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    media_path = str(tmp_path / 'uploads')

    os.environ['SECRET_KEY'] = 'test-secret-key-milestone10-impl'
    os.environ['DATABASE_PATH'] = db_path
    os.environ['MEDIA_PATH'] = media_path
    os.environ['ENABLE_EMAIL_EXPORT'] = 'true'

    import importlib
    import app.email_export as ee_mod
    importlib.reload(ee_mod)

    from app import create_app
    application = create_app()
    application.config['TESTING'] = True
    application.config['SESSION_COOKIE_SECURE'] = False

    with application.app_context():
        from app.database import create_user
        create_user('alice', 'correct-horse-battery')
        create_user('bob', 'correct-horse-battery')

    yield application

    os.unlink(db_path)
    os.environ.pop('MEDIA_PATH', None)
    os.environ.pop('ENABLE_EMAIL_EXPORT', None)
    importlib.reload(ee_mod)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def enabled_client(app_enabled):
    return app_enabled.test_client()


@pytest.fixture()
def auth_client(client):
    client.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
    return client


@pytest.fixture()
def auth_enabled_client(enabled_client, app_enabled):
    enabled_client.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
    # Patch _FEATURE_ENABLED in the email_export module
    import app.email_export as ee_mod
    ee_mod._FEATURE_ENABLED = True
    return enabled_client


def make_note(c, title='Test Note', body='Hello world'):
    r = c.post('/api/notes', json={'title': title, 'body': body})
    assert r.status_code == 201
    return r.get_json()


# ---------------------------------------------------------------------------
# Feature flag OFF — email-pdf returns 403
# ---------------------------------------------------------------------------

class TestEmailPdfFlagOff:
    def test_requires_auth(self, client):
        r = client.post('/api/notes/1/email-pdf')
        assert r.status_code in (302, 401)

    def test_returns_403_when_flag_off(self, auth_client):
        note = make_note(auth_client)
        r = auth_client.post(f'/api/notes/{note["id"]}/email-pdf')
        assert r.status_code == 403
        data = r.get_json()
        assert 'feature' in data
        assert data['feature'] == 'email_pdf'

    def test_returns_json_content_type(self, auth_client):
        note = make_note(auth_client)
        r = auth_client.post(f'/api/notes/{note["id"]}/email-pdf')
        assert r.content_type.startswith('application/json')


# ---------------------------------------------------------------------------
# Feature flag OFF — batch-export returns 403
# ---------------------------------------------------------------------------

class TestBatchExportFlagOff:
    def test_requires_auth(self, client):
        r = client.post('/api/batch-export', json={'note_ids': [1]})
        assert r.status_code in (302, 401)

    def test_returns_403_when_flag_off(self, auth_client):
        r = auth_client.post('/api/batch-export', json={'note_ids': [1]})
        assert r.status_code == 403
        data = r.get_json()
        assert data['feature'] == 'batch_export'


# ---------------------------------------------------------------------------
# Email PDF — feature flag ON
# ---------------------------------------------------------------------------

class TestEmailPdfEnabled:
    def _patch_send(self):
        return patch('app.email_export._send_email')

    def test_requires_auth(self, enabled_client):
        import app.email_export as ee_mod
        ee_mod._FEATURE_ENABLED = True
        r = enabled_client.post('/api/notes/1/email-pdf')
        assert r.status_code in (302, 401)

    def test_returns_400_if_no_email_configured(self, auth_enabled_client):
        # alice has no email yet
        note = make_note(auth_enabled_client)
        with self._patch_send() as mock_send:
            r = auth_enabled_client.post(f'/api/notes/{note["id"]}/email-pdf')
        assert r.status_code == 400
        assert 'email' in r.get_json()['error'].lower()

    def test_returns_404_for_other_users_note(self, app_enabled):
        import app.email_export as ee_mod
        ee_mod._FEATURE_ENABLED = True
        # Create note as alice, try to email as bob
        with app_enabled.test_client() as alice_c:
            alice_c.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
            note = make_note(alice_c)

        with app_enabled.test_client() as bob_c:
            bob_c.post('/login', data={'username': 'bob', 'password': 'correct-horse-battery'})
            # Set bob's email
            bob_c.post('/api/settings/email', json={'email': 'bob@example.com'})
            with self._patch_send():
                r = bob_c.post(f'/api/notes/{note["id"]}/email-pdf')
            assert r.status_code == 404

    def test_sends_email_successfully(self, auth_enabled_client):
        # Set alice's email first
        auth_enabled_client.post('/api/settings/email', json={'email': 'alice@example.com'})
        note = make_note(auth_enabled_client)
        with self._patch_send() as mock_send:
            r = auth_enabled_client.post(f'/api/notes/{note["id"]}/email-pdf')
        assert r.status_code == 200
        data = r.get_json()
        assert data['ok'] is True
        assert data['to'] == 'alice@example.com'
        mock_send.assert_called_once()
        # Verify the call arguments
        args = mock_send.call_args[0]
        assert args[0] == 'alice@example.com'    # to_address
        assert 'Test Note' in args[1]             # subject
        assert args[4].endswith('.pdf')           # attachment filename

    def test_rate_limit_returns_429(self, auth_enabled_client, app_enabled):
        auth_enabled_client.post('/api/settings/email', json={'email': 'alice@example.com'})
        note = make_note(auth_enabled_client)
        # Insert 10 fake log entries directly
        with app_enabled.app_context():
            from app.database import get_db
            db = get_db()
            uid = db.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
            for _ in range(10):
                db.execute(
                    'INSERT INTO email_send_log (user_id, note_id) VALUES (?, ?)',
                    (uid, note['id'])
                )
            db.commit()

        with self._patch_send():
            r = auth_enabled_client.post(f'/api/notes/{note["id"]}/email-pdf')
        assert r.status_code == 429
        assert 'rate limit' in r.get_json()['error'].lower()

    def test_smtp_error_returns_500(self, auth_enabled_client):
        auth_enabled_client.post('/api/settings/email', json={'email': 'alice@example.com'})
        note = make_note(auth_enabled_client)
        with patch('app.email_export._send_email',
                   side_effect=smtplib.SMTPException('connection refused')):
            r = auth_enabled_client.post(f'/api/notes/{note["id"]}/email-pdf')
        assert r.status_code == 500
        data = r.get_json()
        assert 'error' in data
        # SMTP details must not be leaked
        assert 'connection refused' not in data['error']

    def test_rate_limit_counter_increments(self, auth_enabled_client, app_enabled):
        """Successful sends are logged for rate limiting."""
        auth_enabled_client.post('/api/settings/email', json={'email': 'alice@example.com'})
        note = make_note(auth_enabled_client)
        with self._patch_send():
            auth_enabled_client.post(f'/api/notes/{note["id"]}/email-pdf')
        with app_enabled.app_context():
            from app.database import get_db
            db = get_db()
            uid = db.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
            count = db.execute(
                "SELECT COUNT(*) FROM email_send_log WHERE user_id = ?", (uid,)
            ).fetchone()[0]
        assert count == 1


# ---------------------------------------------------------------------------
# Settings — email address endpoints
# ---------------------------------------------------------------------------

class TestSettingsEmail:
    def test_requires_auth_get(self, client):
        r = client.get('/api/settings/email')
        assert r.status_code in (302, 401)

    def test_requires_auth_post(self, client):
        r = client.post('/api/settings/email', json={'email': 'a@b.com'})
        assert r.status_code in (302, 401)

    def test_get_returns_empty_initially(self, auth_client):
        r = auth_client.get('/api/settings/email')
        assert r.status_code == 200
        assert r.get_json()['email'] == ''

    def test_save_and_get_email(self, auth_client):
        r = auth_client.post('/api/settings/email', json={'email': 'alice@test.com'})
        assert r.status_code == 200
        assert r.get_json()['ok'] is True
        r2 = auth_client.get('/api/settings/email')
        assert r2.get_json()['email'] == 'alice@test.com'

    def test_clear_email(self, auth_client):
        auth_client.post('/api/settings/email', json={'email': 'alice@test.com'})
        auth_client.post('/api/settings/email', json={'email': ''})
        r = auth_client.get('/api/settings/email')
        assert r.get_json()['email'] == ''

    def test_invalid_email_returns_400(self, auth_client):
        r = auth_client.post('/api/settings/email', json={'email': 'not-an-email'})
        assert r.status_code == 400

    def test_email_too_long_returns_400(self, auth_client):
        long_email = 'a' * 250 + '@b.com'
        r = auth_client.post('/api/settings/email', json={'email': long_email})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Batch Export — feature flag ON
# ---------------------------------------------------------------------------

class TestBatchExportEnabled:
    def test_empty_note_ids_returns_400(self, auth_enabled_client):
        import app.email_export as ee_mod
        ee_mod._FEATURE_ENABLED = True
        r = auth_enabled_client.post('/api/batch-export',
                                     json={'note_ids': [], 'format': 'zip'})
        assert r.status_code == 400

    def test_over_limit_returns_400(self, auth_enabled_client):
        import app.email_export as ee_mod
        ee_mod._FEATURE_ENABLED = True
        ids = list(range(1, 52))  # 51 IDs
        r = auth_enabled_client.post('/api/batch-export',
                                     json={'note_ids': ids, 'format': 'zip'})
        assert r.status_code == 400
        assert '50' in r.get_json()['error']

    def test_invalid_format_returns_400(self, auth_enabled_client):
        import app.email_export as ee_mod
        ee_mod._FEATURE_ENABLED = True
        note = make_note(auth_enabled_client)
        r = auth_enabled_client.post('/api/batch-export',
                                     json={'note_ids': [note['id']], 'format': 'docx'})
        assert r.status_code == 400

    def test_other_users_note_returns_404(self, app_enabled):
        import app.email_export as ee_mod
        ee_mod._FEATURE_ENABLED = True
        with app_enabled.test_client() as alice_c:
            alice_c.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
            note = make_note(alice_c)

        with app_enabled.test_client() as bob_c:
            bob_c.post('/login', data={'username': 'bob', 'password': 'correct-horse-battery'})
            r = bob_c.post('/api/batch-export',
                           json={'note_ids': [note['id']], 'format': 'zip'})
            assert r.status_code == 404

    def test_zip_format_returns_zip(self, auth_enabled_client):
        import app.email_export as ee_mod
        ee_mod._FEATURE_ENABLED = True
        n1 = make_note(auth_enabled_client, 'Note One', 'Body one')
        n2 = make_note(auth_enabled_client, 'Note Two', 'Body two')
        r = auth_enabled_client.post('/api/batch-export',
                                     json={'note_ids': [n1['id'], n2['id']], 'format': 'zip'})
        assert r.status_code == 200
        assert 'application/zip' in r.content_type
        assert 'attachment' in r.headers.get('Content-Disposition', '')
        zf = zipfile.ZipFile(io.BytesIO(r.data))
        names = zf.namelist()
        assert len(names) == 2
        for name in names:
            assert name.endswith('.pdf')

    def test_zip_contains_valid_pdfs(self, auth_enabled_client):
        import app.email_export as ee_mod
        ee_mod._FEATURE_ENABLED = True
        note = make_note(auth_enabled_client, 'My Note', 'Content here')
        r = auth_enabled_client.post('/api/batch-export',
                                     json={'note_ids': [note['id']], 'format': 'zip'})
        zf = zipfile.ZipFile(io.BytesIO(r.data))
        pdf_bytes = zf.read(zf.namelist()[0])
        assert pdf_bytes[:4] == b'%PDF'

    def test_pdf_format_returns_pdf(self, auth_enabled_client):
        import app.email_export as ee_mod
        ee_mod._FEATURE_ENABLED = True
        n1 = make_note(auth_enabled_client, 'Alpha', 'First note')
        n2 = make_note(auth_enabled_client, 'Beta', 'Second note')
        r = auth_enabled_client.post('/api/batch-export',
                                     json={'note_ids': [n1['id'], n2['id']], 'format': 'pdf'})
        assert r.status_code == 200
        assert 'application/pdf' in r.content_type
        assert 'attachment' in r.headers.get('Content-Disposition', '')
        assert r.data[:4] == b'%PDF'

    def test_default_format_is_zip(self, auth_enabled_client):
        import app.email_export as ee_mod
        ee_mod._FEATURE_ENABLED = True
        note = make_note(auth_enabled_client)
        r = auth_enabled_client.post('/api/batch-export',
                                     json={'note_ids': [note['id']]})
        assert r.status_code == 200
        assert 'application/zip' in r.content_type

    def test_duplicate_titles_get_unique_filenames(self, auth_enabled_client):
        import app.email_export as ee_mod
        ee_mod._FEATURE_ENABLED = True
        n1 = make_note(auth_enabled_client, 'Same Title', 'A')
        n2 = make_note(auth_enabled_client, 'Same Title', 'B')
        r = auth_enabled_client.post('/api/batch-export',
                                     json={'note_ids': [n1['id'], n2['id']], 'format': 'zip'})
        assert r.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(r.data))
        names = zf.namelist()
        assert len(names) == 2
        assert len(set(names)) == 2  # names must be unique


# ---------------------------------------------------------------------------
# build_pdf_bytes helper — direct unit test
# ---------------------------------------------------------------------------

class TestBuildPdfBytesHelper:
    def test_export_pdf_route_still_works(self, auth_client):
        note = make_note(auth_client, 'My PDF Note', 'Some body text')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.content_type == 'application/pdf'
        assert r.data[:4] == b'%PDF'

    def test_build_pdf_bytes_directly(self, app):
        """build_pdf_bytes returns valid PDF bytes for a plain note."""
        with app.app_context():
            from app.pdf import build_pdf_bytes, _register_fonts
            _register_fonts()
            note = {
                'title': 'Direct Test',
                'body': 'Line one\nLine two',
                'created_at': '2025-01-01 00:00:00',
                'updated_at': '2025-01-02 00:00:00',
            }
            pdf_bytes = build_pdf_bytes(note, [], '/tmp')
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:4] == b'%PDF'
        assert len(pdf_bytes) > 1000

    def test_build_pdf_bytes_empty_note(self, app):
        """build_pdf_bytes handles empty title and body gracefully."""
        with app.app_context():
            from app.pdf import build_pdf_bytes, _register_fonts
            _register_fonts()
            note = {
                'title': '',
                'body': '',
                'created_at': '',
                'updated_at': '',
            }
            pdf_bytes = build_pdf_bytes(note, [], '/tmp')
        assert pdf_bytes[:4] == b'%PDF'
