import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(__name__, instance_relative_config=False)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['DATABASE_PATH'] = os.environ.get(
        'DATABASE_PATH',
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'notes.db')
    )

    from .database import init_db, close_db
    init_db(app)
    app.teardown_appcontext(close_db)

    from .routes import bp
    app.register_blueprint(bp)

    return app
