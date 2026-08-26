"""Regression checks for the image-upload request contract and diagnostics."""
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "relative_path",
    ["app/static/js/app.js", "dist/app/static/js/app.js"],
)
def test_upload_uses_same_origin_session_and_handles_non_json(relative_path):
    source = (ROOT / relative_path).read_text(encoding="utf-8")

    assert "`/api/notes/${currentNoteId}/images`" in source
    assert "window.location.origin" in source
    assert "credentials: 'same-origin'" in source
    assert "headers: { 'Accept': 'application/json' }" in source
    assert "res.redirected" in source
    assert "contentType.includes('application/json')" in source
    assert "Server blocked the upload (403)" in source
    assert "Upload endpoint not found (404)" in source
    assert "Check Plesk logs and upload-folder permissions" in source


def test_flask_upload_route_matches_frontend_url():
    source = (ROOT / "app/media.py").read_text(encoding="utf-8")

    assert "@media_bp.route('/api/notes/<int:note_id>/images', methods=['POST'])" in source
    assert "request.files['image']" in source


def test_no_cross_origin_cors_is_required():
    source = (ROOT / "app/__init__.py").read_text(encoding="utf-8")

    assert '"connect-src \'self\'; "' in source
    assert "Access-Control-Allow-Origin" not in source
