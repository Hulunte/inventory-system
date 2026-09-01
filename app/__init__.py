from flask import Flask

from config import Config
from app.extensions import db, migrate


def create_app(config_class=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if config_class is not None:
        app.config.from_object(config_class)

    db.init_app(app)

    from app import models

    migrate.init_app(app, db)

    from app.routes.workers import workers_bp
    from app.routes.harvest import harvest_bp
    from app.routes.admin import admin_bp
    from app.routes.history import history_bp
    from app.routes.reports import reports_bp
    from app.routes.views import views_bp

    app.register_blueprint(workers_bp)
    app.register_blueprint(harvest_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(views_bp)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app
