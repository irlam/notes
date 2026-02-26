"""Tests for Milestone 6: PWA installability, offline basics, and sync queue."""
import json
import os
import tempfile
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-abcdef1234567890')


# ---------------------------------------------------------------------------
# Fixtures (match pattern from test_milestone4.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def app(tmp_path):
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    media_path = str(tmp_path / 'uploads')

    os.environ['SECRET_KEY'] = 'test-secret-key-abcdef1234567890'
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


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(app):
    """Authenticated test client for user 'alice'."""
    c = app.test_client()
    c.post('/login', data={'username': 'alice', 'password': 'correct-horse-battery'})
    return c


# ---------------------------------------------------------------------------
# PWA manifest
# ---------------------------------------------------------------------------

class TestPWAManifest:
    def test_manifest_served(self, client):
        """Static manifest.json is accessible."""
        res = client.get('/static/manifest.json')
        assert res.status_code == 200

    def test_manifest_content_type(self, client):
        """manifest.json is served as JSON."""
        res = client.get('/static/manifest.json')
        assert 'json' in res.content_type or 'javascript' in res.content_type

    def test_manifest_required_fields(self, client):
        """Manifest contains all required PWA installability fields."""
        res = client.get('/static/manifest.json')
        data = json.loads(res.data)
        assert data.get('name'), 'name is required'
        assert data.get('short_name'), 'short_name is required'
        assert data.get('start_url'), 'start_url is required'
        assert data.get('display') in ('standalone', 'fullscreen', 'minimal-ui'), \
            'display must be standalone, fullscreen, or minimal-ui'
        assert data.get('icons'), 'icons list is required'
        assert len(data['icons']) >= 2, 'at least two icon sizes required'

    def test_manifest_icons_have_required_sizes(self, client):
        """Manifest includes 192px and 512px icons as required by Chrome."""
        res = client.get('/static/manifest.json')
        data = json.loads(res.data)
        sizes = [icon.get('sizes') for icon in data.get('icons', [])]
        assert '192x192' in sizes, '192x192 icon required'
        assert '512x512' in sizes, '512x512 icon required'

    def test_manifest_maskable_icons(self, client):
        """Manifest includes at least one maskable icon for Android adaptive icons."""
        res = client.get('/static/manifest.json')
        data = json.loads(res.data)
        purposes = [icon.get('purpose', '') for icon in data.get('icons', [])]
        assert any('maskable' in p for p in purposes), \
            'At least one maskable icon required for full installability'

    def test_manifest_has_scope(self, client):
        """Manifest declares a scope."""
        res = client.get('/static/manifest.json')
        data = json.loads(res.data)
        assert 'scope' in data, 'scope field is required for installability'

    def test_manifest_has_background_and_theme_color(self, client):
        """Manifest includes background_color and theme_color for splash screen."""
        res = client.get('/static/manifest.json')
        data = json.loads(res.data)
        assert data.get('background_color'), 'background_color required'
        assert data.get('theme_color'), 'theme_color required'


# ---------------------------------------------------------------------------
# Service worker
# ---------------------------------------------------------------------------

class TestServiceWorker:
    def test_sw_served(self, client):
        """Service worker file is accessible at the registered path."""
        res = client.get('/static/sw.js')
        assert res.status_code == 200

    def test_sw_is_javascript(self, client):
        """Service worker is served as JavaScript."""
        res = client.get('/static/sw.js')
        assert 'javascript' in res.content_type or 'text' in res.content_type

    def test_sw_has_install_handler(self, client):
        """Service worker registers an install event handler."""
        res = client.get('/static/sw.js')
        assert b'install' in res.data

    def test_sw_has_fetch_handler(self, client):
        """Service worker registers a fetch event handler."""
        res = client.get('/static/sw.js')
        assert b'fetch' in res.data

    def test_sw_caches_app_shell(self, client):
        """Service worker defines an APP_SHELL cache list."""
        res = client.get('/static/sw.js')
        assert b'APP_SHELL' in res.data

    def test_sw_has_api_offline_fallback(self, client):
        """Service worker returns offline JSON for API calls when network fails."""
        res = client.get('/static/sw.js')
        assert b'Offline' in res.data


# ---------------------------------------------------------------------------
# Dashboard and PWA meta tags
# ---------------------------------------------------------------------------

class TestDashboardPWA:
    def test_dashboard_has_manifest_link(self, auth_client):
        """Dashboard template includes manifest link tag."""
        res = auth_client.get('/dashboard')
        assert res.status_code == 200
        assert b'manifest.json' in res.data

    def test_dashboard_has_theme_color(self, auth_client):
        """Dashboard template includes theme-color meta tag."""
        res = auth_client.get('/dashboard')
        assert b'theme-color' in res.data

    def test_dashboard_has_apple_touch_icon(self, auth_client):
        """Dashboard template includes apple-touch-icon for iOS PWA."""
        res = auth_client.get('/dashboard')
        assert b'apple-touch-icon' in res.data

    def test_dashboard_has_apple_mobile_web_app_capable(self, auth_client):
        """Dashboard template includes apple-mobile-web-app-capable meta tag."""
        res = auth_client.get('/dashboard')
        assert b'apple-mobile-web-app-capable' in res.data

    def test_dashboard_has_offline_banner(self, auth_client):
        """Dashboard includes the offline banner element."""
        res = auth_client.get('/dashboard')
        assert b'offline-banner' in res.data

    def test_dashboard_loads_sync_js(self, auth_client):
        """Dashboard loads sync.js before app.js."""
        res = auth_client.get('/dashboard')
        assert b'sync.js' in res.data
        content = res.data.decode()
        sync_pos = content.find('sync.js')
        app_pos = content.find('app.js')
        assert sync_pos < app_pos, 'sync.js must be loaded before app.js'


# ---------------------------------------------------------------------------
# Sync JS module (static file)
# ---------------------------------------------------------------------------

class TestSyncJs:
    def test_sync_js_served(self, client):
        """sync.js is accessible."""
        res = client.get('/static/js/sync.js')
        assert res.status_code == 200

    def test_sync_js_exports_SyncQueue(self, client):
        """sync.js defines and exports window.SyncQueue."""
        res = client.get('/static/js/sync.js')
        assert b'SyncQueue' in res.data

    def test_sync_js_has_enqueue(self, client):
        """sync.js exposes enqueueSave function."""
        res = client.get('/static/js/sync.js')
        assert b'enqueueSave' in res.data

    def test_sync_js_has_process_queue(self, client):
        """sync.js exposes processSyncQueue function."""
        res = client.get('/static/js/sync.js')
        assert b'processSyncQueue' in res.data

    def test_sync_js_has_get_sync_status(self, client):
        """sync.js exposes getSyncStatus function."""
        res = client.get('/static/js/sync.js')
        assert b'getSyncStatus' in res.data

    def test_sync_js_has_offline_cache(self, client):
        """sync.js includes offline cache functions."""
        res = client.get('/static/js/sync.js')
        assert b'cacheNotesData' in res.data
        assert b'getCachedNotesData' in res.data

    def test_sync_js_has_conflict_copy_support(self, client):
        """sync.js includes conflict copy handling in processSyncQueue."""
        res = client.get('/static/js/sync.js')
        assert b'conflict' in res.data.lower()

    def test_sync_js_has_diagnostics(self, client):
        """sync.js includes diagnostic helpers for debugging."""
        res = client.get('/static/js/sync.js')
        assert b'getDiagnostics' in res.data
        assert b'logDiagnostics' in res.data


# ---------------------------------------------------------------------------
# PWA icons
# ---------------------------------------------------------------------------

class TestPWAIcons:
    def test_icon_192_served(self, client):
        """192x192 PWA icon is accessible."""
        res = client.get('/static/icons/icon-192.png')
        assert res.status_code == 200

    def test_icon_512_served(self, client):
        """512x512 PWA icon is accessible."""
        res = client.get('/static/icons/icon-512.png')
        assert res.status_code == 200

    def test_icon_192_is_png(self, client):
        """192x192 icon is a PNG file."""
        res = client.get('/static/icons/icon-192.png')
        assert res.data[:4] == b'\x89PNG' or res.data[:8] == b'\x89PNG\r\n\x1a\n'

    def test_icon_512_is_png(self, client):
        """512x512 icon is a PNG file."""
        res = client.get('/static/icons/icon-512.png')
        assert res.data[:4] == b'\x89PNG' or res.data[:8] == b'\x89PNG\r\n\x1a\n'
