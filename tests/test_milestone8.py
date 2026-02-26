"""Tests for Milestone 8: Hardening, QA, polish, and operational readiness."""
import os
import tempfile
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-milestone8-xyz123')


@pytest.fixture()
def app(tmp_path):
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    media_path = str(tmp_path / 'uploads')

    os.environ['SECRET_KEY'] = 'test-secret-key-milestone8-xyz123'
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


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    def test_x_frame_options_deny(self, client):
        r = client.get('/login')
        assert r.headers.get('X-Frame-Options') == 'DENY'

    def test_x_content_type_nosniff(self, client):
        r = client.get('/login')
        assert r.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_referrer_policy(self, client):
        r = client.get('/login')
        assert 'strict-origin' in r.headers.get('Referrer-Policy', '')

    def test_permissions_policy(self, client):
        r = client.get('/login')
        pp = r.headers.get('Permissions-Policy', '')
        assert 'camera=()' in pp
        assert 'microphone=()' in pp

    def test_csp_present(self, client):
        r = client.get('/login')
        csp = r.headers.get('Content-Security-Policy', '')
        assert "default-src 'self'" in csp

    def test_headers_present_on_api(self, auth_client):
        r = auth_client.get('/api/notes')
        assert r.headers.get('X-Frame-Options') == 'DENY'
        assert r.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_headers_present_on_static(self, client):
        r = client.get('/static/manifest.json')
        assert r.headers.get('X-Content-Type-Options') == 'nosniff'


# ---------------------------------------------------------------------------
# 413 error handler
# ---------------------------------------------------------------------------

class TestRequestTooLarge:
    def test_oversized_upload_returns_413(self, auth_client, app):
        note = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()
        # Temporarily lower MAX_CONTENT_LENGTH
        original = app.config['MAX_CONTENT_LENGTH']
        app.config['MAX_CONTENT_LENGTH'] = 100  # 100 bytes — tiny
        import io
        r = auth_client.post(
            f'/api/notes/{note["id"]}/images',
            data={'image': (io.BytesIO(b'x' * 200), 'photo.jpg', 'image/jpeg')},
            content_type='multipart/form-data',
        )
        app.config['MAX_CONTENT_LENGTH'] = original
        assert r.status_code == 413

    def test_413_response_is_json_for_api(self, auth_client, app):
        note = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()
        original = app.config['MAX_CONTENT_LENGTH']
        app.config['MAX_CONTENT_LENGTH'] = 100
        import io
        r = auth_client.post(
            f'/api/notes/{note["id"]}/images',
            data={'image': (io.BytesIO(b'x' * 200), 'photo.jpg', 'image/jpeg')},
            content_type='multipart/form-data',
        )
        app.config['MAX_CONTENT_LENGTH'] = original
        if r.status_code == 413:
            assert r.is_json


# ---------------------------------------------------------------------------
# Input length validation
# ---------------------------------------------------------------------------

class TestInputLengthValidation:
    def test_title_too_long_returns_400(self, auth_client):
        r = auth_client.post('/api/notes', json={
            'title': 'x' * 501,
            'body': '',
        })
        assert r.status_code == 400

    def test_body_too_long_returns_400(self, auth_client):
        r = auth_client.post('/api/notes', json={
            'title': 'Test',
            'body': 'x' * 100_001,
        })
        assert r.status_code == 400

    def test_title_at_max_length_is_accepted(self, auth_client):
        r = auth_client.post('/api/notes', json={
            'title': 'x' * 500,
            'body': '',
        })
        assert r.status_code == 201

    def test_body_at_max_length_is_accepted(self, auth_client):
        r = auth_client.post('/api/notes', json={
            'title': 'Test',
            'body': 'x' * 100_000,
        })
        assert r.status_code == 201

    def test_update_title_too_long_returns_400(self, auth_client):
        note = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()
        r = auth_client.put(f'/api/notes/{note["id"]}', json={
            'title': 'x' * 501,
            'body': '',
        })
        assert r.status_code == 400

    def test_update_body_too_long_returns_400(self, auth_client):
        note = auth_client.post('/api/notes', json={'title': 'T', 'body': ''}).get_json()
        r = auth_client.put(f'/api/notes/{note["id"]}', json={
            'title': 'T',
            'body': 'x' * 100_001,
        })
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Settings page
# ---------------------------------------------------------------------------

class TestSettingsPage:
    def test_requires_login(self, client):
        r = client.get('/settings')
        assert r.status_code == 302

    def test_settings_page_loads(self, auth_client):
        r = auth_client.get('/settings')
        assert r.status_code == 200

    def test_settings_page_contains_username(self, auth_client):
        r = auth_client.get('/settings')
        assert b'alice' in r.data

    def test_settings_page_has_password_form(self, auth_client):
        r = auth_client.get('/settings')
        assert b'current-pw' in r.data or b'current_password' in r.data or b'password' in r.data.lower()


# ---------------------------------------------------------------------------
# Change password endpoint
# ---------------------------------------------------------------------------

class TestChangePassword:
    def test_requires_login(self, client):
        r = client.post('/api/settings/password', json={
            'current_password': 'correct-horse-battery',
            'new_password': 'NewPass123!',
            'confirm_password': 'NewPass123!',
        })
        assert r.status_code == 302

    def test_change_password_success(self, auth_client):
        r = auth_client.post('/api/settings/password', json={
            'current_password': 'correct-horse-battery',
            'new_password': 'NewPass123!',
            'confirm_password': 'NewPass123!',
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('ok') is True

    def test_wrong_current_password_returns_400(self, auth_client):
        r = auth_client.post('/api/settings/password', json={
            'current_password': 'wrong-password',
            'new_password': 'NewPass123!',
            'confirm_password': 'NewPass123!',
        })
        assert r.status_code == 400
        assert 'error' in r.get_json()

    def test_mismatched_new_passwords_returns_400(self, auth_client):
        r = auth_client.post('/api/settings/password', json={
            'current_password': 'correct-horse-battery',
            'new_password': 'NewPass123!',
            'confirm_password': 'DifferentPass!',
        })
        assert r.status_code == 400
        data = r.get_json()
        assert 'match' in data['error'].lower()

    def test_short_new_password_returns_400(self, auth_client):
        r = auth_client.post('/api/settings/password', json={
            'current_password': 'correct-horse-battery',
            'new_password': 'short',
            'confirm_password': 'short',
        })
        assert r.status_code == 400
        data = r.get_json()
        assert '8' in data['error']

    def test_missing_fields_returns_400(self, auth_client):
        r = auth_client.post('/api/settings/password', json={})
        assert r.status_code == 400

    def test_password_actually_changes(self, app):
        """After changing password, old password no longer works."""
        c = app.test_client()
        c.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
        c.post('/api/settings/password', json={
            'current_password': 'correct-horse-battery',
            'new_password': 'NewStrongPass99!',
            'confirm_password': 'NewStrongPass99!',
        })
        c.post('/logout')

        # Old password should fail
        r = c.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
        # Should not redirect to dashboard
        assert r.headers.get('Location', '') != '/dashboard'

        # New password should succeed
        r2 = c.post('/login', data={'username': 'alice', 'password': 'NewStrongPass99!'})
        assert '/dashboard' in r2.headers.get('Location', '')

    def test_long_password_returns_400(self, auth_client):
        r = auth_client.post('/api/settings/password', json={
            'current_password': 'correct-horse-battery',
            'new_password': 'x' * 129,
            'confirm_password': 'x' * 129,
        })
        assert r.status_code == 400
