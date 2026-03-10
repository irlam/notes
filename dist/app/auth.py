from functools import wraps

from flask import (
    Blueprint, flash, redirect, render_template,
    request, session, url_for
)

from .database import get_user_by_username, verify_password

auth_bp = Blueprint('auth', __name__)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def login_required(f):
    """Redirect to login page when the session carries no authenticated user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = get_user_by_username(username) if username else None
        if user is None or not user['is_active'] or not verify_password(user, password):
            # Deliberately vague – do not reveal which field was wrong
            error = 'Invalid username or password.'
        else:
            session.clear()
            session['user_id'] = user['id']
            session.permanent = True

            next_url = request.form.get('next') or request.args.get('next', '')
            # Reject absolute URLs to prevent open-redirect attacks
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('main.dashboard'))

    return render_template('login.html', error=error,
                           next=request.args.get('next', ''))


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
