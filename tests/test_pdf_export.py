"""Phase 3: PDF export tests — layout, regression, and smoke checks.

These tests validate:
  1. HTTP-level correctness of the PDF export endpoint.
  2. PDF content correctness using pypdf text extraction.
  3. Multi-page, long-body, special-character, and checklist fixtures.
  4. Golden sample: seeded fixture with deterministic content.
"""
import io
import os
import tempfile

import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key-pdf-export-suite')

# ---------------------------------------------------------------------------
# Attempt to import pypdf for text extraction; skip extraction tests if absent
# ---------------------------------------------------------------------------
try:
    import pypdf as _pypdf
    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False

pypdf_required = pytest.mark.skipif(
    not _PYPDF_AVAILABLE,
    reason='pypdf not installed; install with: pip install pypdf',
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app(tmp_path):
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    media_path = str(tmp_path / 'uploads')
    os.makedirs(media_path, exist_ok=True)

    os.environ['SECRET_KEY'] = 'test-secret-key-pdf-export-suite'
    os.environ['DATABASE_PATH'] = db_path
    os.environ['MEDIA_PATH'] = media_path

    from app import create_app
    application = create_app()
    application.config['TESTING'] = True
    application.config['SESSION_COOKIE_SECURE'] = False

    with application.app_context():
        from app.database import create_user
        create_user('testuser', 'correct-horse-battery')

    yield application

    os.unlink(db_path)
    os.environ.pop('MEDIA_PATH', None)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(client):
    client.post('/login', data={'username': 'testuser', 'password': 'correct-horse-battery'})
    return client


def _make_note(c, title='Test Note', body='Hello world'):
    r = c.post('/api/notes', json={'title': title, 'body': body})
    assert r.status_code == 201
    return r.get_json()


def _extract_text(pdf_bytes):
    """Return all text extracted from the given PDF bytes via pypdf."""
    reader = _pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return '\n'.join(
        (page.extract_text() or '') for page in reader.pages
    )


def _page_count(pdf_bytes):
    reader = _pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages)


# ---------------------------------------------------------------------------
# 1. HTTP-level correctness
# ---------------------------------------------------------------------------

class TestPdfExportHTTP:
    def test_requires_auth(self, client):
        r = client.get('/api/notes/1/export.pdf')
        assert r.status_code in (302, 401)

    def test_returns_200(self, auth_client):
        note = _make_note(auth_client)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200

    def test_content_type_is_pdf(self, auth_client):
        note = _make_note(auth_client)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.content_type == 'application/pdf'

    def test_response_starts_with_pdf_magic(self, auth_client):
        note = _make_note(auth_client)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.data[:4] == b'%PDF'

    def test_content_disposition_attachment(self, auth_client):
        note = _make_note(auth_client, title='My Note')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        cd = r.headers.get('Content-Disposition', '')
        assert 'attachment' in cd

    def test_returns_404_for_unowned_note(self, app):
        """A user cannot export another user's note."""
        with app.app_context():
            from app.database import create_user
            create_user('otheruser', 'correct-horse-battery')

        with app.test_client() as alice_c:
            alice_c.post('/login', data={'username': 'testuser', 'password': 'correct-horse-battery'})
            note = _make_note(alice_c)

        with app.test_client() as bob_c:
            bob_c.post('/login', data={'username': 'otheruser', 'password': 'correct-horse-battery'})
            r = bob_c.get(f'/api/notes/{note["id"]}/export.pdf')
            assert r.status_code == 404

    def test_returns_404_for_nonexistent_note(self, auth_client):
        r = auth_client.get('/api/notes/99999/export.pdf')
        assert r.status_code == 404

    def test_pdf_is_non_empty(self, auth_client):
        note = _make_note(auth_client, body='Some content')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert len(r.data) > 500


# ---------------------------------------------------------------------------
# 2. PDF content correctness (requires pypdf)
# ---------------------------------------------------------------------------

class TestPdfContent:
    @pypdf_required
    def test_title_appears_in_pdf(self, auth_client):
        note = _make_note(auth_client, title='Unique Title XYZ', body='Body text here')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        text = _extract_text(r.data)
        assert 'Unique Title XYZ' in text

    @pypdf_required
    def test_body_text_appears_in_pdf(self, auth_client):
        note = _make_note(auth_client, title='Title', body='Distinctive body content ABCDEF')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        text = _extract_text(r.data)
        assert 'Distinctive body content ABCDEF' in text

    @pypdf_required
    def test_checklist_items_appear_in_pdf(self, auth_client):
        body = '[ ] Buy milk\n[x] Send email\n[ ] Call dentist'
        note = _make_note(auth_client, title='Checklist', body=body)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        text = _extract_text(r.data)
        assert 'Buy milk' in text
        assert 'Send email' in text

    @pypdf_required
    def test_pdf_has_at_least_one_page(self, auth_client):
        note = _make_note(auth_client, title='One Page', body='Short note.')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert _page_count(r.data) >= 1

    @pypdf_required
    def test_extracted_text_not_empty(self, auth_client):
        note = _make_note(auth_client, title='Content Note', body='Hello world')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        text = _extract_text(r.data)
        assert len(text.strip()) > 0

    @pypdf_required
    def test_special_characters_in_title_and_body(self, auth_client):
        """HTML-special characters must be escaped, not break PDF generation."""
        note = _make_note(
            auth_client,
            title='Title & "Quotes" <Test>',
            body='Body with <b>bold</b> & ampersand',
        )
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'

    @pypdf_required
    def test_untitled_note_shows_untitled(self, auth_client):
        note = _make_note(auth_client, title='', body='No title here')
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        text = _extract_text(r.data)
        assert 'Untitled' in text


# ---------------------------------------------------------------------------
# 3. Long-content / multi-page regression
# ---------------------------------------------------------------------------

class TestPdfLongContent:
    @pypdf_required
    def test_long_body_produces_valid_pdf(self, auth_client):
        """A note with many lines must produce a valid PDF (no crash, no blank)."""
        lines = [f'Line {i}: ' + 'lorem ipsum dolor sit amet ' * 5 for i in range(200)]
        body = '\n'.join(lines)
        note = _make_note(auth_client, title='Long Note', body=body)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'
        assert _page_count(r.data) >= 2

    @pypdf_required
    def test_long_body_wraps_text(self, auth_client):
        """A line that is longer than the page width must appear in extracted text."""
        long_line = 'A' * 300
        note = _make_note(auth_client, title='Wrap Test', body=long_line)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        assert r.data[:4] == b'%PDF'
        text = _extract_text(r.data)
        # At least part of the long line must appear
        assert 'A' * 10 in text

    @pypdf_required
    def test_page_count_bounded_for_long_content(self, auth_client):
        """500 lines of content should fit in a reasonable number of pages."""
        lines = [f'Line {i}: short text.' for i in range(500)]
        body = '\n'.join(lines)
        note = _make_note(auth_client, title='Bounded Pages', body=body)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200
        count = _page_count(r.data)
        # 500 short lines at 11pt/16 leading on A4 ≈ 3–10 pages max
        assert 1 <= count <= 15


# ---------------------------------------------------------------------------
# 4. Golden fixture — deterministic seeded content
# ---------------------------------------------------------------------------

GOLDEN_TITLE = 'Golden Note: Café & "Special" <Chars> Ü'
GOLDEN_BODY = """\
This is the first paragraph of the golden note.
It spans a single line.

Second paragraph with a blank line above.
[ ] Unchecked item one
[x] Checked item two
[ ] Unchecked item three

A third paragraph with unicode: café, résumé, naïve, über.

Long line follows:
""" + ('x' * 120) + '\n' + '\n'.join(
    f'Numbered line {i}: the quick brown fox jumps over the lazy dog.' for i in range(1, 51)
)

GOLDEN_TITLE_SAFE = 'Golden Note'  # substring safe for text extraction check


class TestGoldenFixture:
    @pypdf_required
    def test_golden_pdf_status_200(self, auth_client):
        note = _make_note(auth_client, title=GOLDEN_TITLE, body=GOLDEN_BODY)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.status_code == 200

    @pypdf_required
    def test_golden_pdf_magic_bytes(self, auth_client):
        note = _make_note(auth_client, title=GOLDEN_TITLE, body=GOLDEN_BODY)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert r.data[:4] == b'%PDF'

    @pypdf_required
    def test_golden_pdf_has_multiple_pages(self, auth_client):
        note = _make_note(auth_client, title=GOLDEN_TITLE, body=GOLDEN_BODY)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        assert _page_count(r.data) >= 2

    @pypdf_required
    def test_golden_pdf_contains_expected_text(self, auth_client):
        note = _make_note(auth_client, title=GOLDEN_TITLE, body=GOLDEN_BODY)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        text = _extract_text(r.data)
        assert 'Golden Note' in text
        assert 'first paragraph' in text
        assert 'Unchecked item one' in text
        assert 'Checked item two' in text

    @pypdf_required
    def test_golden_pdf_text_length_threshold(self, auth_client):
        """Extracted text should be substantial — not a blank or near-blank PDF."""
        note = _make_note(auth_client, title=GOLDEN_TITLE, body=GOLDEN_BODY)
        r = auth_client.get(f'/api/notes/{note["id"]}/export.pdf')
        text = _extract_text(r.data)
        assert len(text.strip()) >= 200


# ---------------------------------------------------------------------------
# 5. build_pdf_bytes unit tests (no HTTP)
# ---------------------------------------------------------------------------

class TestBuildPdfBytesUnit:
    def test_returns_bytes(self, app):
        with app.app_context():
            from app.pdf import build_pdf_bytes, _register_fonts
            _register_fonts()
            note = {
                'title': 'Unit Test',
                'body': 'Unit body',
                'created_at': '2025-01-01 10:00:00',
                'updated_at': '2025-01-02 10:00:00',
            }
            result = build_pdf_bytes(note, [], '/tmp')
        assert isinstance(result, bytes)

    def test_starts_with_pdf_magic(self, app):
        with app.app_context():
            from app.pdf import build_pdf_bytes, _register_fonts
            _register_fonts()
            note = {
                'title': 'Magic Test',
                'body': 'Body here',
                'created_at': '2025-01-01',
                'updated_at': '2025-01-01',
            }
            result = build_pdf_bytes(note, [], '/tmp')
        assert result[:4] == b'%PDF'

    def test_empty_title_and_body(self, app):
        with app.app_context():
            from app.pdf import build_pdf_bytes, _register_fonts
            _register_fonts()
            note = {'title': '', 'body': '', 'created_at': '', 'updated_at': ''}
            result = build_pdf_bytes(note, [], '/tmp')
        assert result[:4] == b'%PDF'

    def test_none_title_and_body(self, app):
        with app.app_context():
            from app.pdf import build_pdf_bytes, _register_fonts
            _register_fonts()
            note = {'title': None, 'body': None, 'created_at': None, 'updated_at': None}
            result = build_pdf_bytes(note, [], '/tmp')
        assert result[:4] == b'%PDF'

    def test_multiline_body_with_checklist(self, app):
        with app.app_context():
            from app.pdf import build_pdf_bytes, _register_fonts
            _register_fonts()
            note = {
                'title': 'Checklist Note',
                'body': '[ ] Item 1\n[x] Item 2\nRegular line',
                'created_at': '2025-01-01',
                'updated_at': '2025-01-01',
            }
            result = build_pdf_bytes(note, [], '/tmp')
        assert result[:4] == b'%PDF'

    def test_html_special_chars_do_not_crash(self, app):
        with app.app_context():
            from app.pdf import build_pdf_bytes, _register_fonts
            _register_fonts()
            note = {
                'title': 'Title & "Test" <Chars>',
                'body': 'Body: <b>bold</b> & ampersand > less-than',
                'created_at': '2025-01-01',
                'updated_at': '2025-01-01',
            }
            result = build_pdf_bytes(note, [], '/tmp')
        assert result[:4] == b'%PDF'

    def test_very_long_single_line(self, app):
        with app.app_context():
            from app.pdf import build_pdf_bytes, _register_fonts
            _register_fonts()
            note = {
                'title': 'Long Line',
                'body': 'A' * 500,
                'created_at': '2025-01-01',
                'updated_at': '2025-01-01',
            }
            result = build_pdf_bytes(note, [], '/tmp')
        assert result[:4] == b'%PDF'
