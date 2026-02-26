"""
app/email_export.py — Milestone 10 stubs: Email PDF and Batch Export.

These endpoints are NOT yet implemented.  They return HTTP 501 Not Implemented
(or 403 Forbidden when the feature flag is disabled) so that the UI can safely
call them and show a "Coming soon" message without causing unhandled errors.

Feature flag:  set ENABLE_EMAIL_EXPORT=true in .env to switch the response
               from 403 to 501.  Neither value enables real functionality;
               both are safe placeholders until M10 is implemented.

Security notes (for full implementation in M10):
  - Must verify authenticated user owns the note before emailing.
  - Must rate-limit email sends per user to prevent abuse.
  - Must NOT act as an open relay; sender address must be fixed (SMTP_FROM).
  - SMTP credentials must come from environment variables only (never committed).
  - Batch export must cap the number of notes per request to prevent DoS.
"""

import os

from flask import Blueprint, jsonify, session
from .auth import login_required

email_export_bp = Blueprint('email_export', __name__)

_FEATURE_ENABLED = os.environ.get('ENABLE_EMAIL_EXPORT', 'false').lower() == 'true'

_NOT_IMPLEMENTED_MSG = (
    'Email PDF export is not yet available. '
    'This feature is planned for Milestone 10.'
)
_BATCH_NOT_IMPLEMENTED_MSG = (
    'Batch export is not yet available. '
    'This feature is planned for Milestone 10.'
)
_DISABLED_MSG = (
    'Email export is not enabled on this server. '
    'Set ENABLE_EMAIL_EXPORT=true in .env to activate (once implemented).'
)


@email_export_bp.route('/api/notes/<int:note_id>/email-pdf', methods=['POST'])
@login_required
def email_pdf(note_id: int):
    """[M10 STUB] Email the PDF export of a note to the authenticated user.

    Returns:
        501 Not Implemented — feature not yet built.
        403 Forbidden      — feature flag is disabled.
    """
    if not _FEATURE_ENABLED:
        return jsonify({'error': _DISABLED_MSG, 'feature': 'email_pdf', 'milestone': 10}), 403
    return jsonify({'error': _NOT_IMPLEMENTED_MSG, 'feature': 'email_pdf', 'milestone': 10}), 501


@email_export_bp.route('/api/batch-export', methods=['POST'])
@login_required
def batch_export():
    """[M10 STUB] Export multiple notes as a ZIP archive or combined PDF.

    Returns:
        501 Not Implemented — feature not yet built.
        403 Forbidden      — feature flag is disabled.
    """
    if not _FEATURE_ENABLED:
        return jsonify({'error': _DISABLED_MSG, 'feature': 'batch_export', 'milestone': 10}), 403
    return jsonify({'error': _BATCH_NOT_IMPLEMENTED_MSG, 'feature': 'batch_export', 'milestone': 10}), 501
