#!/usr/bin/env python3
"""PDF export smoke test — generates a sample PDF to /tmp for manual review.

Run from the repo root:
    PYTHONPATH=_pydeps SECRET_KEY=test python scripts/smoke_pdf.py

The output PDF is written to /tmp/smoke_pdf_output.pdf (or the path given
as the first CLI argument).  Open it in a PDF viewer to visually verify
the layout: margins, fonts, title, timestamps, body text, and checklist items.
"""
import io
import os
import sys

# Ensure _pydeps is on the path when run directly
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYDEPS = os.path.join(REPO_ROOT, '_pydeps')
for p in (PYDEPS, REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault('SECRET_KEY', 'smoke-test-key-not-for-production')

from app.pdf import build_pdf_bytes, _register_fonts  # noqa: E402

_SMOKE_NOTE = {
    'title': 'Smoke Test Note — Café & "Special" Chars <Ü>',
    'body': (
        'This is the first paragraph of the smoke-test note.\n'
        'It has multiple lines to verify line wrapping works correctly.\n'
        '\n'
        'Second paragraph after a blank line.\n'
        '\n'
        '[ ] Unchecked task item\n'
        '[x] Checked/completed task item\n'
        '[ ] Another unchecked item\n'
        '\n'
        'Unicode test: café, résumé, naïve, über, Ångström, 日本語テスト\n'
        '\n'
        'Long line (should wrap within page margins):\n'
        + ('The quick brown fox jumps over the lazy dog. ' * 8).strip() + '\n'
        '\n'
        + '\n'.join(
            f'Numbered line {i:03d}: lorem ipsum dolor sit amet, '
            'consectetur adipiscing elit, sed do eiusmod tempor incididunt.'
            for i in range(1, 61)
        )
    ),
    'created_at': '2025-01-15 09:30:00',
    'updated_at': '2025-06-20 14:45:00',
}


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/smoke_pdf_output.pdf'

    print(f'Registering fonts...', flush=True)
    _register_fonts()

    print(f'Generating PDF for note: {_SMOKE_NOTE["title"]!r}', flush=True)
    pdf_bytes = build_pdf_bytes(_SMOKE_NOTE, [], '/tmp')

    with open(out_path, 'wb') as fh:
        fh.write(pdf_bytes)

    print(f'PDF written to: {out_path} ({len(pdf_bytes):,} bytes)', flush=True)
    print('Open the file in a PDF viewer to verify the layout.', flush=True)

    # Basic sanity checks
    assert pdf_bytes[:4] == b'%PDF', 'PDF does not start with %PDF magic bytes!'
    assert len(pdf_bytes) > 1000, f'PDF too small: {len(pdf_bytes)} bytes'
    print('Sanity checks passed.', flush=True)


if __name__ == '__main__':
    main()
