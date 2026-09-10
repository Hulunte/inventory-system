import logging
import os
import signal
import socket
import sys
import threading
import time
import traceback
import webbrowser


LOG_DIR = "logs"
LOG_FILE = "inventory-system.log"


def _get_base_dir():
    """Get the base directory for logs and other files."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _setup_logging():
    """Configure logging to file and stderr. Must be called early."""
    base = _get_base_dir()
    log_dir = os.path.join(base, LOG_DIR)
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, LOG_FILE)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logging.root.addHandler(file_handler)
    except Exception:
        pass
    logging.root.setLevel(logging.INFO)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logging.root.addHandler(stderr_handler)
    return logging.getLogger("production")


def _is_windowed_mode():
    """Check if running as a PyInstaller windowed (no-console) app."""
    if not getattr(sys, "frozen", False):
        return False
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return ctypes.windll.kernel32.GetConsoleWindow() == 0
    except Exception:
        return False


def _show_error_messagebox(title, message):
    """Show a Windows MessageBox for critical errors in windowed mode."""
    if _is_windowed_mode():
        try:
            import ctypes
            MB_ICONERROR = 0x10
            MB_TOPMOST = 0x40000
            ctypes.windll.user32.MessageBoxW(0, message, title, MB_ICONERROR | MB_TOPMOST)
        except Exception:
            pass


def _is_port_open(host, port, timeout=1.0):
    """Return True if the given host:port is accepting TCP connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, OSError):
        return False


def _open_browser(host, port, path="", max_wait=30):
    """Poll until the server listens, then open the browser once."""
    url = "http://{}:{}{}".format(host, port, path)
    for _ in range(max_wait):
        if _is_port_open(host, port):
            webbrowser.open(url)
            return True
        time.sleep(0.5)
    logging.getLogger("production").warning(
        "Server did not start within %ds, browser not opened", max_wait
    )
    return False


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


def _is_setup_needed():
    """Check if the application needs first-run configuration."""
    admin_hash = os.environ.get("ADMIN_PASSWORD_HASH", "")
    return not admin_hash or admin_hash == "replace-with-generated-password-hash"


def _validate_minimal_config():
    """Validate only the variables needed for the setup wizard to run.

    The setup wizard needs DATABASE_URL, SECRET_KEY, and HARVEST_TIMEZONE
    but NOT ADMIN_PASSWORD_HASH (that is what the wizard configures).
    """
    environ = os.environ

    db_url = environ.get("DATABASE_URL") or ""
    if not db_url:
        raise SystemExit("ERROR: DATABASE_URL is not configured")
    if _has_leading_or_trailing_whitespace(db_url):
        raise SystemExit("ERROR: DATABASE_URL must not contain leading or trailing whitespace")

    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import ArgumentError
    try:
        url = make_url(db_url)
    except ArgumentError:
        raise SystemExit("ERROR: DATABASE_URL has an invalid format")
    if url.get_backend_name() != "postgresql":
        raise SystemExit("ERROR: DATABASE_URL must use PostgreSQL")

    secret_key = environ.get("SECRET_KEY") or ""
    if not secret_key:
        raise SystemExit("ERROR: SECRET_KEY is not configured")
    if _has_leading_or_trailing_whitespace(secret_key):
        raise SystemExit("ERROR: SECRET_KEY must not contain leading or trailing whitespace")
    if len(secret_key) < 32:
        raise SystemExit("ERROR: SECRET_KEY must be at least 32 characters")

    tz_name = environ.get("HARVEST_TIMEZONE") or ""
    if not tz_name:
        raise SystemExit("ERROR: HARVEST_TIMEZONE is not configured")
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError, ValueError):
        raise SystemExit("ERROR: HARVEST_TIMEZONE is not a valid timezone")


def _verify_database_connection(db_url):
    """Authenticate against the configured database before starting the UI."""
    from sqlalchemy import create_engine, text

    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logging.getLogger("production").exception("PostgreSQL connection validation failed")
        raise SystemExit(
            "ERROR: No se pudo conectar de forma autenticada a PostgreSQL. "
            "Revise el servicio y DATABASE_URL."
        ) from exc
    finally:
        engine.dispose()


def _get_bundled_migrations_dir():
    """Return and validate the migration tree embedded by PyInstaller."""
    bundle_dir = getattr(sys, "_MEIPASS", _get_base_dir())
    migrations_dir = os.path.join(bundle_dir, "migrations")
    required = (
        os.path.join(migrations_dir, "alembic.ini"),
        os.path.join(migrations_dir, "env.py"),
        os.path.join(migrations_dir, "versions"),
    )
    missing = [path for path in required if not os.path.exists(path)]
    if missing:
        raise RuntimeError(
            "Incomplete bundled migration tree: "
            + ", ".join(os.path.basename(path) for path in missing)
        )
    return migrations_dir


def _migration_revisions(app, migrations_dir):
    """Read database and script revisions without changing the database."""
    from alembic.config import Config as AlembicConfig
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from app.extensions import db

    ini_path = os.path.join(migrations_dir, "alembic.ini")
    config = AlembicConfig(ini_path)
    config.set_main_option("script_location", migrations_dir)
    target_heads = tuple(ScriptDirectory.from_config(config).get_heads())
    with app.app_context():
        with db.engine.connect() as connection:
            current_heads = tuple(MigrationContext.configure(connection).get_current_heads())
    return current_heads, target_heads


def _redacted_traceback(db_url):
    """Format the active exception while removing database credentials."""
    rendered = traceback.format_exc()
    if db_url:
        rendered = rendered.replace(db_url, "<redacted DATABASE_URL>")
        try:
            from sqlalchemy.engine import make_url

            password = make_url(db_url).password
            if password:
                rendered = rendered.replace(password, "***")
        except Exception:
            pass
    return rendered


def _run_pending_migrations(app):
    """Apply pending Alembic migrations and verify that the DB reaches head."""
    from flask_migrate import upgrade

    logger = logging.getLogger("production")
    db_url = app.config.get("SQLALCHEMY_DATABASE_URI") or os.environ.get("DATABASE_URL", "")
    migrations_dir = "<unresolved>"
    current_heads = ("<unavailable>",)
    target_heads = ("<unavailable>",)
    try:
        migrations_dir = _get_bundled_migrations_dir()
        current_heads, target_heads = _migration_revisions(app, migrations_dir)
        logger.info("Alembic ini: %s", os.path.join(migrations_dir, "alembic.ini"))
        logger.info("Alembic script_location: %s", migrations_dir)
        logger.info("Alembic current revision(s): %s", current_heads or ("base",))
        logger.info("Alembic target revision(s): %s", target_heads)
        with app.app_context():
            upgrade(directory=migrations_dir)
        final_heads, _ = _migration_revisions(app, migrations_dir)
        if set(final_heads) != set(target_heads):
            raise RuntimeError(
                "Alembic upgrade finished without reaching head: "
                f"current={final_heads!r}, target={target_heads!r}"
            )
        logger.info("Alembic database verified at head: %s", final_heads)
    except Exception as exc:
        logger.error(
            "Alembic migration failed: type=%s current=%s target=%s "
            "script_location=%s\n%s",
            type(exc).__name__,
            current_heads,
            target_heads,
            migrations_dir,
            _redacted_traceback(db_url),
        )
        raise SystemExit(
            "ERROR: No se pudieron aplicar las migraciones pendientes. "
            "La aplicacion no se iniciara. Revise logs/inventory-system.log."
        ) from exc


def main():
    logger = _setup_logging()

    from dotenv import load_dotenv, find_dotenv
    base = _get_base_dir()

    if getattr(sys, "frozen", False):
        env_path = os.path.join(base, ".env")
        if os.path.isfile(env_path):
            load_dotenv(env_path, override=False)
        else:
            logger.warning("No .env file found at %s — setup wizard will be available", env_path)
    else:
        env_file = find_dotenv(usecwd=True)
        if env_file:
            load_dotenv(env_file, override=False)
        else:
            load_dotenv(override=False)

    import secrets as _secrets
    if not os.environ.get("SECRET_KEY"):
        os.environ["SECRET_KEY"] = _secrets.token_hex(32)
        logger.info("Generated temporary SECRET_KEY (will be persisted by setup wizard)")

    setup_needed = _is_setup_needed()

    if setup_needed:
        logger.info("First-run detected: ADMIN_PASSWORD_HASH not configured")
        logger.info("Starting setup wizard mode")
        try:
            _validate_minimal_config()
        except SystemExit as exc:
            error_msg = str(exc)
            logger.error("Startup error (setup mode): %s", error_msg)
            _show_error_messagebox("Inventory System - Error", error_msg)
            raise
    else:
        try:
            validate_production_config()
        except SystemExit as exc:
            error_msg = str(exc)
            logger.error("Startup error: %s", error_msg)
            _show_error_messagebox("Inventory System - Error", error_msg)
            raise

    if getattr(sys, "frozen", False):
        try:
            _verify_database_connection(os.environ["DATABASE_URL"])
        except SystemExit as exc:
            _show_error_messagebox("Inventory System - PostgreSQL", str(exc))
            raise

    host = os.getenv("APP_HOST", "0.0.0.0")
    port_str = os.getenv("APP_PORT", "5000")
    try:
        port = int(port_str)
        if not (1 <= port <= 65535):
            raise ValueError("Port {} outside valid range 1-65535".format(port))
    except ValueError as exc:
        error_msg = "ERROR: APP_PORT='{}' must be an integer in range 1-65535".format(port_str)
        logger.error("Startup error: %s", error_msg)
        _show_error_messagebox("Inventory System - Error", error_msg)
        raise SystemExit(error_msg)

    from app import create_app
    app = create_app()
    app.debug = False

    if getattr(sys, "frozen", False):
        try:
            _run_pending_migrations(app)
        except SystemExit as exc:
            _show_error_messagebox("Inventory System - Migraciones", str(exc))
            raise

    logger.info("Starting inventory-system on %s:%d", host, port)
    logger.info("Debug mode: DISABLED")
    if setup_needed:
        logger.info("Setup wizard available at http://%s:%d/setup", host, port)

    from waitress import create_server
    server = create_server(app, host=host, port=port)

    server_ready = threading.Event()

    def _run_server():
        server_ready.set()
        server.run()

    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()
    server_ready.wait(timeout=5)

    if __name__ == "__main__":
        browser_host = host if host != "0.0.0.0" else "127.0.0.1"
        browser_path = "/setup" if setup_needed else "/"
        threading.Thread(
            target=_open_browser,
            args=(browser_host, port, browser_path),
            daemon=True,
        ).start()

    shutdown_event = threading.Event()

    def _shutdown_handler(signum, _frame):
        logger.info("Received signal %s, shutting down...", signum)
        server.close()
        shutdown_event.set()

    signal.signal(signal.SIGINT, _shutdown_handler)
    if sys.platform == "win32":
        try:
            signal.signal(signal.SIGBREAK, _shutdown_handler)
        except AttributeError:
            pass

    try:
        shutdown_event.wait()
    except KeyboardInterrupt:
        server.close()

    logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        # A windowed PyInstaller executable otherwise displays an additional
        # fatal-error dialog containing only the process exit code (usually
        # "1"). The actionable message was already shown and the complete,
        # credential-redacted traceback was already written to the app log.
        if getattr(sys, "frozen", False):
            exit_code = exc.code if isinstance(exc.code, int) else 1
            os._exit(exit_code)
        raise
