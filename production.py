import os


def main():
    # Production entrypoint — Waitress WSGI server
    # Nunca arranca Flask debug server bajo ninguna circunstancia

    # Configuración segura por defecto
    host = os.getenv("APP_HOST", "0.0.0.0")

    # APP_PORT con validación estricta
    port_str = os.getenv("APP_PORT", "5000")
    try:
        port = int(port_str)
        if not (1 <= port <= 65535):
            raise ValueError(
                f"Port {port} outside valid range 1-65535"
            )
    except ValueError:
        raise SystemExit(
            f"ERROR: APP_PORT='{port_str}' must be an integer in range 1-65535"
        )

    # Crear aplicación mediante el application factory existente
    from app import create_app
    app = create_app()

    # ¡DEBUG ESTÁ EXPLÍCITAMENTE DESHABILITADO!
    # No hay fallback, no hay Werkzeug dev server
    # Flask app object: debug is False by default; we ensure it
    app.debug = False

    # Importar serve dentro de main() para facilitar el mocking en tests
    from waitress import serve
    serve(app, host=host, port=port)


if __name__ == "__main__":
    main()