"""Regression checks for the durable offline-first browser integration."""
from pathlib import Path


ROOT = Path(__file__).parents[1]
APP_JS = (ROOT / 'app' / 'static' / 'js' / 'app.js').read_text(encoding='utf-8')
SW_JS = (ROOT / 'app' / 'static' / 'sw.js').read_text(encoding='utf-8')


def test_indexeddb_persists_notes_images_and_operations():
    assert "indexedDB.open('notes-pwa', 2)" in APP_JS
    for store in ('cached_notes', 'cached_images', 'pending_writes', 'pending_ops'):
        assert f"'{store}'" in APP_JS


def test_offline_mutations_are_queued():
    for operation in ('create_note', 'trash_note', 'upload_image', 'delete_image'):
        assert f"type: '{operation}'" in APP_JS


def test_queued_edits_include_conflict_base_timestamp():
    assert 'client_updated_at: w.client_updated_at' in APP_JS
    assert 'client_updated_at: note.updated_at' in APP_JS


def test_reconnect_and_startup_flush_durable_queue():
    assert "window.addEventListener('online', updateOnlineStatus)" in APP_JS
    assert 'Promise.all([getPendingWrites(), getPendingOperations()])' in APP_JS


def test_service_worker_caches_full_install_shell():
    assert "CACHE_NAME = 'notes-v5'" in SW_JS
    for asset in (
        '/dashboard', '/static/css/style.css', '/static/js/app.js',
        '/static/manifest.json', '/static/icons/favicon.ico',
        '/static/icons/apple-touch-icon.png',
        '/static/icons/android-chrome-192x192.png',
        '/static/icons/android-chrome-512x512.png',
        '/static/icons/maskable-icon-192x192.png',
        '/static/icons/maskable-icon-512x512.png',
    ):
        assert asset in SW_JS
