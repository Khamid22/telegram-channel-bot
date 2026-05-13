from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from admin.extensions import login_manager
from admin.state import reload_scheduler
from admin.routes import auth, drive, posts, schedules, generator, templates, assets
from config.settings import BASE_DIR, get_settings


def create_app(start_background_scheduler: bool = False) -> Flask:
    settings = get_settings()
    static_dir = BASE_DIR / "admin" / "static"
    app = Flask(__name__, static_folder=str(static_dir), static_url_path="")
    app.secret_key = settings.secret_key
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    CORS(app, supports_credentials=True)

    login_manager.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(drive.bp)
    app.register_blueprint(posts.bp)
    app.register_blueprint(schedules.bp)
    app.register_blueprint(generator.bp)
    app.register_blueprint(templates.bp)
    app.register_blueprint(assets.bp)

    if start_background_scheduler:
        reload_scheduler()

    return app
