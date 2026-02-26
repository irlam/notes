from flask import (
    Blueprint, render_template, request, jsonify, session, redirect, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from .auth import login_required
from .database import get_db, get_user_by_id, get_user_email, set_user_email

settings_bp = Blueprint('settings', __name__)

_MIN_PASSWORD_LEN = 8
_MAX_PASSWORD_LEN = 128


def _current_user_id():
    return session['user_id']


@settings_bp.route('/settings')
@login_required
def settings_page():
    user = get_user_by_id(_current_user_id())
    return render_template('settings.html',
                           username=user['username'] if user else '',
                           user_email=user['email'] if user else '')


@settings_bp.route('/api/settings/password', methods=['POST'])
@login_required
def change_password():
    """Change the current user's password.

    Request JSON: {current_password, new_password, confirm_password}
    """
    data = request.get_json(silent=True) or {}
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')
    confirm_pw = data.get('confirm_password', '')

    if not current_pw or not new_pw or not confirm_pw:
        return jsonify({'error': 'All fields are required.'}), 400

    if new_pw != confirm_pw:
        return jsonify({'error': 'New passwords do not match.'}), 400

    if len(new_pw) < _MIN_PASSWORD_LEN:
        return jsonify(
            {'error': f'Password must be at least {_MIN_PASSWORD_LEN} characters.'}
        ), 400

    if len(new_pw) > _MAX_PASSWORD_LEN:
        return jsonify({'error': 'Password is too long.'}), 400

    db = get_db()
    row = db.execute(
        'SELECT id, password_hash FROM users WHERE id = ?', (_current_user_id(),)
    ).fetchone()
    if row is None or not check_password_hash(row['password_hash'], current_pw):
        return jsonify({'error': 'Current password is incorrect.'}), 400

    new_hash = generate_password_hash(new_pw)
    db.execute(
        'UPDATE users SET password_hash = ? WHERE id = ?',
        (new_hash, _current_user_id())
    )
    db.commit()
    return jsonify({'ok': True})


@settings_bp.route('/api/settings/email', methods=['GET'])
@login_required
def get_email():
    """Return the current user's stored email address."""
    return jsonify({'email': get_user_email(_current_user_id()) or ''})


@settings_bp.route('/api/settings/email', methods=['POST'])
@login_required
def update_email():
    """Update the current user's email address.

    Request JSON: {email}
    """
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    if email and ('@' not in email or len(email) > 254):
        return jsonify({'error': 'Invalid email address.'}), 400
    set_user_email(_current_user_id(), email or None)
    return jsonify({'ok': True, 'email': email or None})
