"""
app/email_export.py — Milestone 10: Email PDF and Batch Export.

Email PDF (POST /api/notes/<id>/email-pdf):
  - Requires ENABLE_EMAIL_EXPORT=true (disabled by default).
  - Generates the note PDF and sends it to the user's registered email address.
  - Rate-limited: at most 10 emails per user per hour.
  - Never emails arbitrary addresses — always to the user's own registered address.
  - SMTP credentials are read from environment variables only (never committed).

Batch Export (POST /api/batch-export):
  - Requires ENABLE_EMAIL_EXPORT=true (re-uses the same feature flag).
  - Accepts {"note_ids": [...], "format": "zip"|"pdf"}.
  - Returns a ZIP archive (one PDF per note) or a single combined PDF.
  - Max 50 notes per request; all must be owned by the authenticated user.

Security notes:
  - Ownership of every note is verified before processing.
  - SMTP failures are caught and logged server-side; credentials never
    appear in response bodies.
  - The feature flag defaults to false; set ENABLE_EMAIL_EXPORT=true to activate.
"""

import io
import os
import smtplib
import zipfile
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Blueprint, jsonify, request, session, current_app, make_response, abort
from .auth import login_required
from .database import get_db, get_user_email

email_export_bp = Blueprint('email_export', __name__)


def _fmt_dt_uk(dt_str):
    """Format a SQLite datetime string as DD/MM/YYYY HH:MM (UK format)."""
    if not dt_str:
        return ''
    timed_fmts = (('%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M'),
                  ('%Y-%m-%dT%H:%M:%S', '%d/%m/%Y %H:%M'),
                  ('%Y-%m-%d %H:%M',    '%d/%m/%Y %H:%M'))
    date_fmts  = (('%Y-%m-%d', '%d/%m/%Y'),)
    for src_fmt, out_fmt in timed_fmts + date_fmts:
        try:
            return datetime.strptime(dt_str.strip(), src_fmt).strftime(out_fmt)
        except ValueError:
            continue
    return dt_str

# ---------------------------------------------------------------------------
# Feature flag  (evaluated at request time, not module load, so tests can
# override it via the module-level constant after reload)
# ---------------------------------------------------------------------------
_FEATURE_ENABLED = os.environ.get('ENABLE_EMAIL_EXPORT', 'false').lower() == 'true'

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------
_RATE_LIMIT_PER_HOUR = 10
_BATCH_MAX_NOTES = 50

_DISABLED_MSG = (
    'Email export is not enabled on this server. '
    'Set ENABLE_EMAIL_EXPORT=true in .env to activate.'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_user_id():
    return session['user_id']


def _check_rate_limit(db, user_id):
    """Return True if the user is within the rate limit, False if exceeded."""
    count = db.execute(
        "SELECT COUNT(*) FROM email_send_log "
        "WHERE user_id = ? AND sent_at > datetime('now', '-1 hour')",
        (user_id,),
    ).fetchone()[0]
    return count < _RATE_LIMIT_PER_HOUR


def _record_send(db, user_id, note_id):
    """Insert a rate-limit log entry."""
    db.execute(
        'INSERT INTO email_send_log (user_id, note_id) VALUES (?, ?)',
        (user_id, note_id),
    )
    db.commit()


def _send_email(to_address, subject, body_text, attachment_bytes, attachment_filename):
    """Send an email with a PDF attachment via SMTP.

    SMTP configuration is read from environment variables:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM

    Raises smtplib.SMTPException (or subclass) on failure.
    """
    smtp_host = os.environ.get('SMTP_HOST', '')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    smtp_from = os.environ.get('SMTP_FROM', smtp_user)

    if not smtp_host:
        raise ValueError('SMTP_HOST is not configured.')

    msg = MIMEMultipart()
    msg['From'] = smtp_from
    msg['To'] = to_address
    msg['Subject'] = subject
    msg.attach(MIMEText(body_text, 'plain'))

    part = MIMEApplication(attachment_bytes, Name=attachment_filename)
    part['Content-Disposition'] = f'attachment; filename="{attachment_filename}"'
    msg.attach(part)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_from, to_address, msg.as_string())


def _safe_filename(title):
    """Return a safe ASCII filename base from *title*."""
    raw = (title or 'note').strip() or 'note'
    safe = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in raw)
    return (safe[:50] or 'note')


def _note_story_elements(note, img_rows, media_path):
    """Return the reportlab story elements for a single note (no PageBreak).

    Used by the combined-PDF batch export path to build one story for all
    notes without creating intermediate PDF bytes.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.platypus import Image as RLImage
    from reportlab.lib import colors
    from .pdf import (
        _FONT_BOLD, _FONT_NORMAL, _safe_text, _composite_annotations,
        _MAX_IMG_HEIGHT_PT,
    )

    page_w, _ = A4
    content_w = page_w - 2 * inch

    style_title = ParagraphStyle(
        'NoteTitle2',
        fontName=_FONT_BOLD,
        fontSize=22, leading=28, spaceAfter=6,
        textColor=colors.HexColor('#1a1a2e'),
    )
    style_meta = ParagraphStyle(
        'NoteMeta2',
        fontName=_FONT_NORMAL,
        fontSize=9, leading=12,
        textColor=colors.HexColor('#6b6b8a'),
        spaceAfter=14,
    )
    style_body = ParagraphStyle(
        'NoteBody2',
        fontName=_FONT_NORMAL,
        fontSize=11, leading=16, spaceAfter=3, wordWrap='LTR',
    )
    style_check = ParagraphStyle(
        'NoteCheck2',
        fontName=_FONT_NORMAL,
        fontSize=11, leading=16, leftIndent=12, spaceAfter=3,
    )
    style_caption = ParagraphStyle(
        'NoteCaption2',
        fontName=_FONT_NORMAL,
        fontSize=8, leading=10,
        textColor=colors.HexColor('#888888'),
        spaceAfter=8,
    )

    story = []
    title_text = (note['title'] or '').strip() or 'Untitled'
    story.append(Paragraph(_safe_text(title_text), style_title))

    created = _fmt_dt_uk(note['created_at'])
    updated = _fmt_dt_uk(note['updated_at'])
    meta = f'Created: {created}'
    if updated and updated != created:
        meta += f'  \u00b7  Updated: {updated}'
    story.append(Paragraph(_safe_text(meta), style_meta))

    body = (note['body'] or '').rstrip()
    if body:
        for line in body.split('\n'):
            stripped = line.rstrip()
            if not stripped:
                story.append(Spacer(1, 6))
                continue
            lower = stripped.lower()
            if lower.startswith('[ ] ') or lower.startswith('[x] '):
                checked = lower.startswith('[x] ')
                item_text = stripped[4:]
                prefix = '[x]' if checked else '[ ]'
                story.append(Paragraph(f'{prefix} {_safe_text(item_text)}', style_check))
            else:
                story.append(Paragraph(_safe_text(stripped), style_body))

    if img_rows:
        story.append(Spacer(1, 14))
        for img_row in img_rows:
            img_path = os.path.join(media_path, img_row['filename'])
            if not os.path.isfile(img_path):
                continue
            annotation_data = img_row['annotation_data']
            composited_bytes = (
                _composite_annotations(img_path, annotation_data)
                if annotation_data else None
            )
            try:
                from PIL import Image as PILImage
                src = io.BytesIO(composited_bytes) if composited_bytes else img_path
                with PILImage.open(src) as pil_img:
                    iw, ih = pil_img.size
            except Exception:
                continue
            if iw <= 0 or ih <= 0:
                continue
            scale = min(content_w / iw, _MAX_IMG_HEIGHT_PT / ih)
            img_src = io.BytesIO(composited_bytes) if composited_bytes else img_path
            story.append(RLImage(img_src, width=iw * scale, height=ih * scale))
            caption = img_row['original_filename'] or ''
            if caption:
                story.append(Paragraph(_safe_text(caption), style_caption))
            story.append(Spacer(1, 10))

            # Section text: paragraph text that appears after this image
            section_text = (img_row['section_text'] or '').rstrip()
            if section_text:
                story.append(Spacer(1, 6))
                for line in section_text.split('\n'):
                    stripped = line.rstrip()
                    if not stripped:
                        story.append(Spacer(1, 6))
                        continue
                    story.append(Paragraph(_safe_text(stripped), style_body))
                story.append(Spacer(1, 10))

    return story


# ---------------------------------------------------------------------------
# Email PDF endpoint
# ---------------------------------------------------------------------------

@email_export_bp.route('/api/notes/<int:note_id>/email-pdf', methods=['POST'])
@login_required
def email_pdf(note_id: int):
    """Email the PDF export of a note to the authenticated user's address.

    Returns
    -------
    200  OK              — email sent successfully.
    400  Bad Request     — user has no email address configured.
    403  Forbidden       — feature flag disabled.
    404  Not Found       — note not found / not owned by current user.
    429  Too Many Reqs   — rate limit exceeded.
    500  Server Error    — SMTP failure.
    """
    if not _FEATURE_ENABLED:
        return jsonify({'error': _DISABLED_MSG, 'feature': 'email_pdf', 'milestone': 10}), 403

    uid = _current_user_id()
    db = get_db()

    # Ownership check
    row = db.execute(
        'SELECT id, title, body, created_at, updated_at '
        'FROM notes WHERE id = ? AND user_id = ? AND is_trashed = 0',
        (note_id, uid),
    ).fetchone()
    if row is None:
        abort(404)

    # Rate limit
    if not _check_rate_limit(db, uid):
        return jsonify({
            'error': (
                f'Rate limit exceeded. '
                f'You may send at most {_RATE_LIMIT_PER_HOUR} emails per hour.'
            ),
        }), 429

    # Destination address — only the user's own registered address
    to_address = get_user_email(uid)
    if not to_address:
        return jsonify({
            'error': (
                'No email address configured. '
                'Add one in Settings before using Email PDF.'
            ),
        }), 400

    # Fetch images for this note
    img_rows = db.execute(
        'SELECT id, filename, original_filename, annotation_data, caption, section_text '
        'FROM note_images WHERE note_id = ? AND user_id = ? '
        'ORDER BY position ASC, id ASC LIMIT 20',
        (note_id, uid),
    ).fetchall()

    # Build PDF
    from .pdf import build_pdf_bytes, _register_fonts
    _register_fonts()
    media_path = current_app.config['MEDIA_PATH']
    note = dict(row)
    pdf_bytes = build_pdf_bytes(note, img_rows, media_path)

    # Send email
    title = note['title'] or 'Untitled'
    filename = _safe_filename(title) + '.pdf'
    subject = f'Note: {title}'
    body = f'Please find your note "{title}" attached as a PDF.'
    try:
        _send_email(to_address, subject, body, pdf_bytes, filename)
    except Exception as exc:
        current_app.logger.error('email_pdf SMTP error: %s', exc)
        return jsonify({'error': 'Failed to send email. Please check SMTP configuration.'}), 500

    _record_send(db, uid, note_id)
    return jsonify({'ok': True, 'to': to_address})


# ---------------------------------------------------------------------------
# Batch export endpoint
# ---------------------------------------------------------------------------

@email_export_bp.route('/api/batch-export', methods=['POST'])
@login_required
def batch_export():
    """Export multiple notes as a ZIP archive or combined PDF.

    Request JSON
    ------------
    {
        "note_ids": [1, 2, 3],
        "format":   "zip" | "pdf"      (default: "zip")
    }

    Returns
    -------
    200  OK (application/zip or application/pdf) — file download.
    400  Bad Request  — empty/over-limit note_ids, invalid format.
    403  Forbidden    — feature flag disabled.
    404  Not Found    — one or more notes not owned by current user.
    """
    if not _FEATURE_ENABLED:
        return jsonify({'error': _DISABLED_MSG, 'feature': 'batch_export', 'milestone': 10}), 403

    data = request.get_json(silent=True) or {}
    note_ids = data.get('note_ids', [])
    fmt = (data.get('format') or 'zip').lower()

    if not isinstance(note_ids, list) or len(note_ids) == 0:
        return jsonify({'error': 'note_ids must be a non-empty list.'}), 400
    if len(note_ids) > _BATCH_MAX_NOTES:
        return jsonify({
            'error': f'Batch export is limited to {_BATCH_MAX_NOTES} notes per request.',
        }), 400
    if fmt not in ('zip', 'pdf'):
        return jsonify({'error': 'format must be "zip" or "pdf".'}), 400

    uid = _current_user_id()
    db = get_db()
    media_path = current_app.config['MEDIA_PATH']

    from .pdf import build_pdf_bytes, _register_fonts
    _register_fonts()

    if fmt == 'zip':
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            seen_names: dict[str, int] = {}
            for note_id in note_ids:
                row = db.execute(
                    'SELECT id, title, body, created_at, updated_at '
                    'FROM notes WHERE id = ? AND user_id = ? AND is_trashed = 0',
                    (note_id, uid),
                ).fetchone()
                if row is None:
                    abort(404)
                note = dict(row)
                img_rows = db.execute(
                    'SELECT id, filename, original_filename, annotation_data, caption, section_text '
                    'FROM note_images WHERE note_id = ? AND user_id = ? '
                    'ORDER BY position ASC, id ASC LIMIT 20',
                    (note_id, uid),
                ).fetchall()
                pdf_bytes = build_pdf_bytes(note, img_rows, media_path)
                base = _safe_filename(note['title'])
                if base not in seen_names:
                    seen_names[base] = 0
                    arc_name = base + '.pdf'
                else:
                    seen_names[base] += 1
                    arc_name = f'{base}_{seen_names[base]}.pdf'
                zf.writestr(arc_name, pdf_bytes)
        buf.seek(0)
        response = make_response(buf.getvalue())
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Content-Disposition'] = 'attachment; filename="notes_export.zip"'
        return response

    else:  # fmt == 'pdf'
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, PageBreak

        combined_buf = io.BytesIO()
        doc = SimpleDocTemplate(
            combined_buf,
            pagesize=A4,
            leftMargin=inch, rightMargin=inch,
            topMargin=inch, bottomMargin=inch,
            title='Notes Export',
        )
        story = []
        first = True
        for note_id in note_ids:
            row = db.execute(
                'SELECT id, title, body, created_at, updated_at '
                'FROM notes WHERE id = ? AND user_id = ? AND is_trashed = 0',
                (note_id, uid),
            ).fetchone()
            if row is None:
                abort(404)
            note = dict(row)
            img_rows = db.execute(
                'SELECT id, filename, original_filename, annotation_data, caption, section_text '
                'FROM note_images WHERE note_id = ? AND user_id = ? '
                'ORDER BY position ASC, id ASC LIMIT 20',
                (note_id, uid),
            ).fetchall()
            if not first:
                story.append(PageBreak())
            first = False
            story.extend(_note_story_elements(note, img_rows, media_path))

        doc.build(story)
        response = make_response(combined_buf.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'attachment; filename="notes_export.pdf"'
        return response
