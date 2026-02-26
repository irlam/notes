"""Tests for authentication and session management (Milestone 1)."""
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


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------

class TestLoginPage:
    def test_get_login_returns_200(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200
        assert b'Sign in' in resp.data

    def test_root_redirects_to_login_when_unauthenticated(self, client):
        resp = client.get('/', follow_redirects=False)
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_dashboard_redirects_to_login_when_unauthenticated(self, client):
        resp = client.get('/dashboard', follow_redirects=False)
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_api_notes_redirects_to_login_when_unauthenticated(self, client):
        resp = client.get('/api/notes', follow_redirects=False)
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']


# ---------------------------------------------------------------------------
# Login / logout
# ---------------------------------------------------------------------------

class TestLoginLogout:
    def _login(self, client, username='alice', password='correct-horse-battery'):
        return client.post('/login', data={'username': username, 'password': password},
                           follow_redirects=False)

    def test_valid_login_redirects_to_dashboard(self, client):
        resp = self._login(client)
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']

    def test_invalid_password_returns_error(self, client):
        resp = client.post('/login',
                           data={'username': 'alice', 'password': 'wrongpassword'},
                           follow_redirects=True)
        assert resp.status_code == 200
        assert b'Invalid username or password' in resp.data

    def test_unknown_user_returns_error(self, client):
        resp = client.post('/login',
                           data={'username': 'nobody', 'password': 'whatever'},
                           follow_redirects=True)
        assert resp.status_code == 200
        assert b'Invalid username or password' in resp.data

    def test_empty_credentials_return_error(self, client):
        resp = client.post('/login', data={'username': '', 'password': ''},
                           follow_redirects=True)
        assert resp.status_code == 200
        assert b'Invalid username or password' in resp.data

    def test_logout_clears_session(self, client):
        self._login(client)
        resp = client.post('/logout', follow_redirects=False)
        assert resp.status_code == 302
        # After logout, dashboard should redirect to login
        resp2 = client.get('/dashboard', follow_redirects=False)
        assert resp2.status_code == 302
        assert '/login' in resp2.headers['Location']

    def test_dashboard_accessible_after_login(self, client):
        self._login(client)
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        assert b'alice' in resp.data

    def test_open_redirect_rejected(self, client):
        """next= with an absolute URL must not be followed."""
        resp = client.post('/login',
                           data={'username': 'alice',
                                 'password': 'correct-horse-battery',
                                 'next': '//evil.example.com'},
                           follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers['Location']
        assert 'evil.example.com' not in location

    def test_login_already_logged_in_redirects_to_dashboard(self, client):
        self._login(client)
        resp = client.get('/login', follow_redirects=False)
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']


# ---------------------------------------------------------------------------
# Session cookie flags
# ---------------------------------------------------------------------------

class TestSessionCookieSecurity:
    def test_session_cookie_httponly(self, app):
        assert app.config['SESSION_COOKIE_HTTPONLY'] is True

    def test_session_cookie_samesite(self, app):
        assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'

    def test_session_cookie_secure_off_in_test(self, app):
        # Secure flag should be configurable (off in dev/test)
        assert app.config['SESSION_COOKIE_SECURE'] is False


# ---------------------------------------------------------------------------
# Protected API routes
# ---------------------------------------------------------------------------

class TestProtectedAPI:
    def _login(self, client):
        client.post('/login', data={'username': 'alice',
                                   'password': 'correct-horse-battery'})

    def test_notes_api_requires_auth(self, client):
        resp = client.get('/api/notes')
        assert resp.status_code == 302

    def test_notes_api_accessible_after_login(self, client):
        self._login(client)
        resp = client.get('/api/notes')
        assert resp.status_code == 200

    def test_create_note_requires_auth(self, client):
        resp = client.post('/api/notes', json={'title': 'x', 'body': 'y'})
        assert resp.status_code == 302

    def test_notes_isolated_between_users(self, app, client):
        """Notes created by alice must not be visible to bob."""
        with app.app_context():
            from app.database import create_user
            create_user('bob', 'bobpassword1')

        # alice creates a note
        client.post('/login', data={'username': 'alice',
                                   'password': 'correct-horse-battery'})
        client.post('/api/notes', json={'title': 'Alice secret', 'body': 'private'})
        client.post('/logout')

        # bob logs in and should see no notes
        client.post('/login', data={'username': 'bob', 'password': 'bobpassword1'})
        resp = client.get('/api/notes')
        assert resp.status_code == 200
        assert resp.get_json() == []
