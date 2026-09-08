import logging
import os
import sys
import time

from flask import Flask, jsonify, request

from config import Config
from app.extensions import db, migrate

logger = logging.getLogger(__name__)


def _check_postgres(uri):
    """Return (ok: bool, message: str)."""
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(uri, pool_pre_ping=True, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True, "ok"
    except Exception as exc:
        msg = str(exc)
        if "could not connect" in msg.lower() or "Connection refused" in msg:
            return False, "PostgreSQL no esta disponible. Verifique que el servicio este corriendo."
        if "authentication failed" in msg.lower():
            return False, "Credenciales de PostgreSQL incorrectas. Verifique DATABASE_URL."
        if "does not exist" in msg.lower():
            return False, "La base de datos no existe. Verifique el nombre en DATABASE_URL."
        return False, f"Error de conexion a PostgreSQL: {msg[:200]}"


def create_app(config_class=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if config_class is not None:
        app.config.from_object(config_class)

    Config._validate_ticket_config(app)

    db.init_app(app)

    from app import models

    migrate.init_app(app, db)

    from app.routes.workers import workers_bp
    from app.routes.harvest import harvest_bp
    from app.routes.admin import admin_bp
    from app.routes.history import history_bp
    from app.routes.reports import reports_bp
    from app.routes.tickets import tickets_bp
    from app.routes.scale import scale_bp
    from app.routes.views import views_bp

    app.register_blueprint(workers_bp)
    app.register_blueprint(harvest_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(scale_bp)
    app.register_blueprint(views_bp)

    _register_error_handlers(app)

    @app.after_request
    def prevent_admin_content_caching(response):
        protected_paths = ("/history", "/reports", "/api/history/", "/api/reports/")
        if request.path in protected_paths[:2] or request.path.startswith(protected_paths[2:]):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.get("/api/health")
    def health():
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
        if not db_uri:
            return jsonify({"status": "degraded", "database": "not_configured"}), 503

        db_ok, db_msg = _check_postgres(db_uri)
        if not db_ok:
            return jsonify({"status": "degraded", "database": db_msg}), 503

        return jsonify({"status": "ok", "database": "connected"}), 200

    return app


def _register_error_handlers(app):
    @app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal server error: %s", error)
        return jsonify({"error": "Error interno del servidor"}), 500

    @app.errorhandler(502)
    def bad_gateway(error):
        return jsonify({"error": "Servicio temporalmente no disponible"}), 502

    @app.errorhandler(503)
    def service_unavailable(error):
        return jsonify({"error": "Servicio no disponible"}), 503
