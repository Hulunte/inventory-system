from flask import Flask

from config import Config
from app.extensions import db, migrate


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from app import models

    migrate.init_app(app, db)

    from app.routes.products import products_bp
    from app.routes.inventory import inventory_bp
    from app.routes.views import views_bp

    app.register_blueprint(products_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(views_bp)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app
