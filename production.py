import os


def _has_leading_or_trailing_whitespace(value):
    """Return True if value has leading or trailing whitespace."""
    return value != value.strip()


def validate_production_config(environ=None):
    """Validate that all mandatory environment variables are correctly configured.

    Must be called BEFORE create_app(). Does not create the Flask app,
    import waitress, or start the server under any circumstance.
    """
    if environ is None:
        environ = os.environ

    # --- DATABASE_URL ---
    db_url = environ.get("DATABASE_URL") or ""
    if not db_url:
        raise SystemExit("ERROR: DATABASE_URL is not configured")

    if _has_leading_or_trailing_whitespace(db_url):
        raise SystemExit("ERROR: DATABASE_URL must not contain leading or trailing whitespace")

    if db_url == "postgresql+psycopg://user:password@localhost:5432/inventory_db":
        raise SystemExit("ERROR: DATABASE_URL contains a placeholder value")

    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import ArgumentError
    try:
        url = make_url(db_url)
    except ArgumentError:
        raise SystemExit("ERROR: DATABASE_URL has an invalid format")

    if url.get_backend_name() != "postgresql":
        raise SystemExit("ERROR: DATABASE_URL must use PostgreSQL")

    # --- SECRET_KEY ---
    secret_key = environ.get("SECRET_KEY") or ""
    if not secret_key:
        raise SystemExit("ERROR: SECRET_KEY is not configured")

    if _has_leading_or_trailing_whitespace(secret_key):
        raise SystemExit("ERROR: SECRET_KEY must not contain leading or trailing whitespace")

    if secret_key == "replace-with-a-real-secret-key":
        raise SystemExit("ERROR: SECRET_KEY contains a placeholder value")

    if len(secret_key) < 32:
        raise SystemExit("ERROR: SECRET_KEY must be at least 32 characters")

    # --- ADMIN_PASSWORD_HASH ---
    admin_hash = environ.get("ADMIN_PASSWORD_HASH") or ""
    if not admin_hash:
        raise SystemExit("ERROR: ADMIN_PASSWORD_HASH is not configured")

    if _has_leading_or_trailing_whitespace(admin_hash):
        raise SystemExit("ERROR: ADMIN_PASSWORD_HASH must not contain leading or trailing whitespace")

    if admin_hash == "replace-with-generated-password-hash":
        raise SystemExit("ERROR: ADMIN_PASSWORD_HASH contains a placeholder value")

    dollar_parts = admin_hash.split("$")
    if len(dollar_parts) != 3:
        raise SystemExit("ERROR: ADMIN_PASSWORD_HASH has an invalid format")

    method_part, salt_part, digest_part = dollar_parts
    if not method_part.startswith(("pbkdf2:", "scrypt:")):
        raise SystemExit("ERROR: ADMIN_PASSWORD_HASH has an invalid format")

    if not salt_part or not digest_part:
        raise SystemExit("ERROR: ADMIN_PASSWORD_HASH has an invalid format")

    # --- HARVEST_TIMEZONE ---
    tz_name = environ.get("HARVEST_TIMEZONE") or ""
    if not tz_name:
        raise SystemExit("ERROR: HARVEST_TIMEZONE is not configured")

    if _has_leading_or_trailing_whitespace(tz_name):
        raise SystemExit("ERROR: HARVEST_TIMEZONE must not contain leading or trailing whitespace")

    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError, ValueError):
        raise SystemExit("ERROR: HARVEST_TIMEZONE is not a valid timezone")

    # --- APP_HOST (optional, default 0.0.0.0) ---
    host_raw = environ.get("APP_HOST")
    if host_raw is not None:
        if _has_leading_or_trailing_whitespace(host_raw):
            raise SystemExit("ERROR: APP_HOST must not contain leading or trailing whitespace")
        if not host_raw:
            raise SystemExit("ERROR: APP_HOST must not be empty")

    # --- SESSION_COOKIE_SECURE (optional, default unset) ---
    session_secure = environ.get("SESSION_COOKIE_SECURE")
    if session_secure is not None:
        if _has_leading_or_trailing_whitespace(session_secure):
            raise SystemExit("ERROR: SESSION_COOKIE_SECURE must not contain leading or trailing whitespace")
        normalized = session_secure.strip().lower()
        if normalized not in ("true", "false"):
            raise SystemExit("ERROR: SESSION_COOKIE_SECURE must be 'true' or 'false'")


def main():
    # Load .env file before reading any environment variables.
    # Must happen before validate_production_config() and APP_HOST/APP_PORT reads.
    from dotenv import load_dotenv
    load_dotenv()

    # Validate mandatory configuration before creating the app.
    # Raises SystemExit immediately if any required variable is missing or invalid.
    validate_production_config()

    host = os.getenv("APP_HOST", "0.0.0.0")

    # APP_PORT with strict validation
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

    # Create the application via the existing factory
    from app import create_app
    app = create_app()

    # Debug is explicitly disabled — no fallback, no Werkzeug dev server
    app.debug = False

    # Import serve inside main() to facilitate mocking in tests
    from waitress import serve
    serve(app, host=host, port=port)


if __name__ == "__main__":
    main()
