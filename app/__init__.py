from flask import Flask


def create_app():
    app = Flask(__name__)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app
