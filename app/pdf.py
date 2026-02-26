"""PDF export for a single note — Milestone 7.

Layout rules
------------
* Page size  : A4 (595 × 842 pt), 1-inch margins on all sides.
* Title      : 22 pt bold, dark colour.
* Timestamps : 9 pt, muted colour, beneath title.
* Body text  : 11 pt, leading 16; lines that start with ``[ ] `` or ``[x] ``
               are rendered as plain-text checkbox items (``[ ]`` / ``[x]``).
* Images     : Scaled to fit the usable page width (≈ 453 pt) while
               preserving aspect ratio; height capped at 400 pt so a single
               image never overflows a page.  At most 20 images are embedded
               to keep memory and generation time bounded.
* Annotations: Composited onto the base image server-side with Pillow before
               embedding, so the PDF faithfully reflects the annotated view.
* Fonts      : DejaVu Sans (or Liberation Sans) is registered if present on
               the host file-system for full Unicode support; falls back to
               Helvetica (Latin-1) otherwise.

Plesk compatibility
-------------------
Only pure-Python dependencies are used: ``reportlab`` (PDF) and ``Pillow``
(already required for image handling).  No external binaries or services.
"""
import io
import json
import math
import os

from flask import Blueprint, abort, make_response, session, current_app
from .auth import login_required
from .database import get_db

pdf_bp = Blueprint('pdf', __name__)

# ---------------------------------------------------------------------------
# Known limits
# ---------------------------------------------------------------------------
_MAX_IMAGES = 20          # guard against OOM / timeout on image-heavy notes
_MAX_IMG_HEIGHT_PT = 400  # max rendered height (pt) per image in the PDF

# ---------------------------------------------------------------------------
# TrueType font discovery (for Unicode body text)
# ---------------------------------------------------------------------------
_TTF_NORMAL = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    '/usr/share/fonts/TTF/DejaVuSans.ttf',
]
_TTF_BOLD = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
]

_fonts_registered = False
_FONT_NORMAL = 'Helvetica'
_FONT_BOLD = 'Helvetica-Bold'


def _register_fonts():
    """Register TrueType fonts once per process for Unicode support."""
    global _fonts_registered, _FONT_NORMAL, _FONT_BOLD
    if _fonts_registered:
        return
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        normal_path = next((p for p in _TTF_NORMAL if os.path.isfile(p)), None)
        bold_path = next((p for p in _TTF_BOLD if os.path.isfile(p)), None)

        if normal_path:
            pdfmetrics.registerFont(TTFont('NoteFont', normal_path))
            _FONT_NORMAL = 'NoteFont'
        if bold_path:
            pdfmetrics.registerFont(TTFont('NoteFont-Bold', bold_path))
            _FONT_BOLD = 'NoteFont-Bold'
    except Exception:
        pass  # stay with Helvetica fallback
    _fonts_registered = True


# ---------------------------------------------------------------------------
# Annotation compositing (Pillow)
# ---------------------------------------------------------------------------

def _hex_to_rgba(hex_color, opacity=1.0):
    """Return an RGBA tuple from a ``#rrggbb`` string."""
    try:
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        r, g, b = 231, 76, 60
    return (r, g, b, int(max(0.0, min(1.0, opacity)) * 255))


def _composite_annotations(img_path, annotation_data):
    """Draw annotation strokes on *img_path* using Pillow.

    Returns JPEG bytes of the composited image, or ``None`` on any error
    (the caller will then embed the original file unchanged).
    """
    try:
        from PIL import Image, ImageDraw

        img = Image.open(img_path).convert('RGBA')
        W, H = img.size

        try:
            data = (json.loads(annotation_data)
                    if isinstance(annotation_data, str)
                    else annotation_data) or {}
        except Exception:
            data = {}

        strokes = data.get('strokes', [])
        if not strokes:
            buf = io.BytesIO()
            img.convert('RGB').save(buf, 'JPEG', quality=85)
            return buf.getvalue()

        overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for stroke in strokes:
            tool = stroke.get('tool', 'pen')
            fill = _hex_to_rgba(stroke.get('color', '#e74c3c'),
                                stroke.get('opacity', 1.0))
            sw = max(1, int(stroke.get('width', 0.006) * H))

            if tool in ('pen', 'highlighter'):
                pts = stroke.get('points', [])
                if len(pts) >= 2:
                    coords = [(p['x'] * W, p['y'] * H) for p in pts]
                    draw.line(coords, fill=fill, width=sw)
                elif len(pts) == 1:
                    cx, cy = pts[0]['x'] * W, pts[0]['y'] * H
                    r2 = sw / 2
                    draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2],
                                 fill=fill)

            elif tool == 'arrow':
                x1, y1 = stroke.get('x1', 0) * W, stroke.get('y1', 0) * H
                x2, y2 = stroke.get('x2', 0) * W, stroke.get('y2', 0) * H
                draw.line([(x1, y1), (x2, y2)], fill=fill, width=sw)
                angle = math.atan2(y2 - y1, x2 - x1)
                head = max(sw * 4, 10)
                spread = math.pi / 6
                draw.polygon([
                    (x2, y2),
                    (x2 - head * math.cos(angle - spread),
                     y2 - head * math.sin(angle - spread)),
                    (x2 - head * math.cos(angle + spread),
                     y2 - head * math.sin(angle + spread)),
                ], fill=fill)

            elif tool == 'rectangle':
                x1, y1 = stroke.get('x1', 0) * W, stroke.get('y1', 0) * H
                x2, y2 = stroke.get('x2', 0) * W, stroke.get('y2', 0) * H
                draw.rectangle(
                    [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)],
                    outline=fill, width=sw,
                )

            elif tool == 'circle':
                x1, y1 = stroke.get('x1', 0) * W, stroke.get('y1', 0) * H
                x2, y2 = stroke.get('x2', 0) * W, stroke.get('y2', 0) * H
                draw.ellipse(
                    [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)],
                    outline=fill, width=sw,
                )

            elif tool == 'text':
                x = stroke.get('x', 0) * W
                y = stroke.get('y', 0) * H
                text = stroke.get('text', '')
                font_size = max(10, int(stroke.get('width', 0.006) * H * 8))
                font = None
                for fp in _TTF_NORMAL:
                    if os.path.isfile(fp):
                        try:
                            from PIL import ImageFont as PILFont
                            font = PILFont.truetype(fp, font_size)
                        except Exception:
                            pass
                        break
                draw.text((x, y), text, fill=fill, font=font)

        composited = Image.alpha_composite(img, overlay).convert('RGB')
        buf = io.BytesIO()
        composited.save(buf, 'JPEG', quality=85)
        return buf.getvalue()

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_user_id():
    return session['user_id']


def _safe_text(text):
    """Escape HTML special characters for use inside a reportlab Paragraph."""
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))


# ---------------------------------------------------------------------------
# Export endpoint
# ---------------------------------------------------------------------------

@pdf_bp.route('/api/notes/<int:note_id>/export.pdf', methods=['GET'])
@login_required
def export_note_pdf(note_id):
    """Generate and return a PDF for the requested note.

    The note must belong to the authenticated user; returns 404 otherwise.
    The response carries ``Content-Disposition: attachment`` so browsers
    prompt a download on desktop and mobile alike.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.platypus import Image as RLImage
    from reportlab.lib import colors

    _register_fonts()

    db = get_db()
    uid = _current_user_id()

    row = db.execute(
        'SELECT id, title, body, created_at, updated_at '
        'FROM notes WHERE id = ? AND user_id = ?',
        (note_id, uid),
    ).fetchone()
    if row is None:
        abort(404)

    note = dict(row)

    img_rows = db.execute(
        'SELECT id, filename, original_filename, annotation_data '
        'FROM note_images WHERE note_id = ? AND user_id = ? '
        'ORDER BY position ASC, id ASC '
        'LIMIT ?',
        (note_id, uid, _MAX_IMAGES),
    ).fetchall()

    # -----------------------------------------------------------------------
    # Build PDF
    # -----------------------------------------------------------------------
    buf = io.BytesIO()
    margin = inch
    page_w, _ = A4
    content_w = page_w - 2 * margin

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
        title=note['title'] or 'Untitled',
    )

    style_title = ParagraphStyle(
        'NoteTitle',
        fontName=_FONT_BOLD,
        fontSize=22,
        leading=28,
        spaceAfter=6,
        textColor=colors.HexColor('#1a1a2e'),
    )
    style_meta = ParagraphStyle(
        'NoteMeta',
        fontName=_FONT_NORMAL,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#6b6b8a'),
        spaceAfter=14,
    )
    style_body = ParagraphStyle(
        'NoteBody',
        fontName=_FONT_NORMAL,
        fontSize=11,
        leading=16,
        spaceAfter=3,
        wordWrap='LTR',
    )
    style_check = ParagraphStyle(
        'NoteCheck',
        fontName=_FONT_NORMAL,
        fontSize=11,
        leading=16,
        leftIndent=12,
        spaceAfter=3,
    )
    style_caption = ParagraphStyle(
        'NoteCaption',
        fontName=_FONT_NORMAL,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#888888'),
        spaceAfter=8,
    )

    story = []

    # Title
    title_text = (note['title'] or '').strip() or 'Untitled'
    story.append(Paragraph(_safe_text(title_text), style_title))

    # Timestamps
    created = note['created_at'] or ''
    updated = note['updated_at'] or ''
    meta = f'Created: {created}'
    if updated and updated != created:
        meta += f'  \u00b7  Updated: {updated}'
    story.append(Paragraph(_safe_text(meta), style_meta))

    # Body
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
                story.append(
                    Paragraph(f'{prefix} {_safe_text(item_text)}', style_check)
                )
            else:
                story.append(Paragraph(_safe_text(stripped), style_body))

    # Images
    if img_rows:
        story.append(Spacer(1, 14))
        media_dir = current_app.config['MEDIA_PATH']

        for img_row in img_rows:
            img_path = os.path.join(media_dir, img_row['filename'])
            if not os.path.isfile(img_path):
                continue

            annotation_data = img_row['annotation_data']
            composited_bytes = (
                _composite_annotations(img_path, annotation_data)
                if annotation_data else None
            )

            # Determine pixel dimensions for correct aspect-ratio scaling
            try:
                from PIL import Image as PILImage
                src = (io.BytesIO(composited_bytes)
                       if composited_bytes else img_path)
                with PILImage.open(src) as pil_img:
                    iw, ih = pil_img.size
            except Exception:
                continue

            if iw <= 0 or ih <= 0:
                continue

            scale = min(content_w / iw, _MAX_IMG_HEIGHT_PT / ih)
            draw_w = iw * scale
            draw_h = ih * scale

            img_src = (io.BytesIO(composited_bytes)
                       if composited_bytes else img_path)
            story.append(RLImage(img_src, width=draw_w, height=draw_h))

            caption = img_row['original_filename'] or ''
            if caption:
                story.append(Paragraph(_safe_text(caption), style_caption))
            story.append(Spacer(1, 10))

    doc.build(story)
    pdf_bytes = buf.getvalue()

    # Derive a safe filename from the note title
    raw = (note['title'] or 'note').strip() or 'note'
    safe = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in raw)
    filename = (safe[:50] or 'note') + '.pdf'

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
