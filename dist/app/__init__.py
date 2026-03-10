import os
from datetime import timedelta

import click
from flask import Flask
from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(__name__, instance_relative_config=False)

    # --- Core config ---
    secret = os.environ.get('SECRET_KEY', '')
    if not secret or secret == 'change-me-to-a-random-secret-key':
        raise RuntimeError(
            'SECRET_KEY environment variable must be set to a strong random value. '
            'Generate one with: python3 -c "import secrets; print(secrets.token_hex(32))"'
        )
    app.config['SECRET_KEY'] = secret
    app.config['DATABASE_PATH'] = os.environ.get(
        'DATABASE_PATH',
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'notes.db')
    )
    app.config['MEDIA_PATH'] = os.environ.get(
        'MEDIA_PATH',
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    )
    # 12 MB hard limit (covers 10 MB image + multipart overhead)
    app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
    app.config['ENABLE_EMAIL_EXPORT'] = (
        os.environ.get('ENABLE_EMAIL_EXPORT', 'false').lower() == 'true'
    )

    # --- Session / cookie security ---
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    # Only transmit session cookie over HTTPS; set SESSION_COOKIE_SECURE=true in production.
    app.config['SESSION_COOKIE_SECURE'] = (
        os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    )
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(
        days=int(os.environ.get('SESSION_LIFETIME_DAYS', '14'))
    )

    # --- Database ---
    from .database import init_db, close_db
    init_db(app)
    app.teardown_appcontext(close_db)

    # --- Blueprints ---
    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .routes import bp
    app.register_blueprint(bp)

    from .media import media_bp
    app.register_blueprint(media_bp)

    from .pdf import pdf_bp
    app.register_blueprint(pdf_bp)

    from .settings import settings_bp
    app.register_blueprint(settings_bp)

    from .versions import versions_bp
    app.register_blueprint(versions_bp)

    from .email_export import email_export_bp
    app.register_blueprint(email_export_bp)

    # --- Security headers ---
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(), payment=()'
        )
        # Content-Security-Policy: allow self + data/blob for images (PWA canvas)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "worker-src 'self';"
        )
        return response

    # --- Global 500 error handler ---
    @app.errorhandler(500)
    def internal_error(e):
        from flask import request as _req, jsonify
        app.logger.exception('Unhandled exception: %s', e)
        if _req.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        from flask import render_template as _rt
        return _rt('error.html', code=500,
                   message='An unexpected error occurred.'), 500

    @app.errorhandler(413)
    def request_entity_too_large(e):
        from flask import request as _req, jsonify
        if _req.path.startswith('/api/'):
            return jsonify({'error': 'File too large (max 10 MB)'}), 413
        return jsonify({'error': 'Request too large'}), 413

    # --- CLI: create initial user ---
    @app.cli.command('create-user')
    @click.argument('username')
    def create_user_cmd(username):
        """Create a new user and prompt for a password."""
        import getpass
        from .database import get_user_by_username, create_user
        with app.app_context():
            if get_user_by_username(username):
                click.echo(f"Error: user '{username}' already exists.", err=True)
                raise SystemExit(1)
            password = getpass.getpass('Password: ')
            confirm = getpass.getpass('Confirm password: ')
            if password != confirm:
                click.echo('Error: passwords do not match.', err=True)
                raise SystemExit(1)
            if len(password) < 8:
                click.echo('Error: password must be at least 8 characters.', err=True)
                raise SystemExit(1)
            uid = create_user(username, password)
            click.echo(f"User '{username}' created with id={uid}.")

    return app
