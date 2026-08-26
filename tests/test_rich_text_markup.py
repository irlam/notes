"""Regression checks for rich-text HTML paste/rendering and PWA cache refresh."""
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "relative_path",
    ["app/static/js/app.js", "dist/app/static/js/app.js"],
)
def test_editor_repairs_escaped_markup_and_handles_html_source_paste(relative_path):
    source = (ROOT / relative_path).read_text(encoding="utf-8")

    assert "function decodeLegacyEscapedMarkup(html)" in source
    assert "function sanitizeNoteHtml(html)" in source
    assert "function prepareNoteHtml(html)" in source
    assert "NOTE_MARKUP_TAG_RE.test(plainText)" in source
    assert "document.execCommand('insertHTML'" in source
    assert "noteBody.innerHTML = preparedBody" in source
    assert "scheduleAutosave();" in source


@pytest.mark.parametrize(
    "relative_path",
    ["app/static/sw.js", "dist/app/static/sw.js"],
)
def test_service_worker_refreshes_app_shell_from_network(relative_path):
    source = (ROOT / relative_path).read_text(encoding="utf-8")

    assert "const CACHE_NAME = 'notes-v3';" in source
    assert "event.request.method !== 'GET'" in source
    assert "url.pathname.startsWith('/api/')" in source
    assert "event.request.mode === 'navigate'" in source
    assert "fetch(event.request).then(response =>" in source
    assert "caches.match(event.request)" in source
