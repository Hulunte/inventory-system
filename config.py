import os
import secrets
import sys
from datetime import timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv, find_dotenv


def _get_base_dir():
    """Return the directory where persistent files (.env, logs) live.

    In a PyInstaller frozen bundle the module's __file__ points to the
    temporary ``_MEIPASS`` extraction directory, so we must use the
    directory that contains the ``.exe`` itself.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


_base = _get_base_dir()

if getattr(sys, "frozen", False):
    _env_path = os.path.join(_base, ".env")
    if os.path.isfile(_env_path):
        load_dotenv(_env_path, override=False)
else:
    _env_file = find_dotenv(usecwd=True)
    if _env_file:
        load_dotenv(_env_file, override=False)
    else:
        load_dotenv(override=False)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    HARVEST_TIMEZONE = ZoneInfo(os.getenv("HARVEST_TIMEZONE", "UTC"))

    ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")

    BACKUP_DIR = os.getenv("BACKUP_DIR")
    PG_DUMP_PATH = os.getenv("PG_DUMP_PATH", "pg_dump")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=4)
    SESSION_REFRESH_EACH_REQUEST = False

    MAIL_SMTP_HOST = os.getenv("MAIL_SMTP_HOST", "smtp.gmail.com")
    MAIL_SMTP_PORT = int(os.getenv("MAIL_SMTP_PORT", "587"))
    MAIL_SMTP_USERNAME = os.getenv("MAIL_SMTP_USERNAME")
    MAIL_SMTP_APP_PASSWORD = os.getenv("MAIL_SMTP_APP_PASSWORD")
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "Sistema de Cosecha")
    MAIL_FROM_ADDRESS = os.getenv("MAIL_FROM_ADDRESS")
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true")
    MAIL_TIMEOUT_SECONDS = int(os.getenv("MAIL_TIMEOUT_SECONDS", "30"))

    TICKET_BUSINESS_NAME = os.getenv("TICKET_BUSINESS_NAME", "Sistema de Cosecha")
    TICKET_FOOTER_TEXT = os.getenv("TICKET_FOOTER_TEXT", "Conserve este comprobante")
    TICKET_PAPER_WIDTH_MM = int(os.getenv("TICKET_PAPER_WIDTH_MM", "80"))
    TICKET_CHARACTERS_PER_LINE = int(os.getenv("TICKET_CHARACTERS_PER_LINE", "48"))
    TICKET_PRINTER_NAME = os.getenv("TICKET_PRINTER_NAME", "")
    TICKET_ENCODING = os.getenv("TICKET_ENCODING", "cp850")
    TICKET_AUTO_CUT = os.getenv("TICKET_AUTO_CUT", "true").lower() == "true"

    SCALE_PORT = os.getenv("SCALE_PORT", "")
    SCALE_BAUDRATE = int(os.getenv("SCALE_BAUDRATE", "9600"))
    SCALE_BYTESIZE = int(os.getenv("SCALE_BYTESIZE", "8"))
    SCALE_PARITY = os.getenv("SCALE_PARITY", "N")
    SCALE_STOPBITS = float(os.getenv("SCALE_STOPBITS", "1"))
    SCALE_TIMEOUT_SECONDS = float(os.getenv("SCALE_TIMEOUT_SECONDS", "1.0"))
    SCALE_LINE_ENCODING = os.getenv("SCALE_LINE_ENCODING", "ascii")
    SCALE_PROFILE = os.getenv("SCALE_PROFILE", "auto")
    SCALE_MIN_WEIGHT_KG = os.getenv("SCALE_MIN_WEIGHT_KG", "0.001")
    SCALE_MAX_WEIGHT_KG = os.getenv("SCALE_MAX_WEIGHT_KG", "999.999")

    @staticmethod
    def _validate_ticket_config(app):
        paper_width = app.config.get("TICKET_PAPER_WIDTH_MM", 80)
        if paper_width not in (58, 80):
            raise ValueError(f"TICKET_PAPER_WIDTH_MM must be 58 or 80, got {paper_width}")

        cpl = app.config.get("TICKET_CHARACTERS_PER_LINE", 48)
        if not isinstance(cpl, int) or cpl < 20 or cpl > 60:
            raise ValueError(f"TICKET_CHARACTERS_PER_LINE must be between 20 and 60, got {cpl}")

        encoding = app.config.get("TICKET_ENCODING", "cp850")
        try:
            "".encode(encoding)
        except (LookupError, UnicodeEncodeError):
            raise ValueError(f"TICKET_ENCODING '{encoding}' is not a valid encoding")

        business_name = app.config.get("TICKET_BUSINESS_NAME", "")
        if len(business_name) > 50:
            raise ValueError(f"TICKET_BUSINESS_NAME must be at most 50 characters, got {len(business_name)}")

        footer_text = app.config.get("TICKET_FOOTER_TEXT", "")
        if len(footer_text) > 60:
            raise ValueError(f"TICKET_FOOTER_TEXT must be at most 60 characters, got {len(footer_text)}")


class ProductionConfig(Config):
    """Production configuration with mandatory env validation."""

    REQUIRED_VARS = ("SECRET_KEY", "DATABASE_URL", "ADMIN_PASSWORD_HASH")

    @classmethod
    def validate(cls):
        missing = [v for v in cls.REQUIRED_VARS if not os.getenv(v)]
        if missing:
            msg = (
                "Faltan variables de entorno obligatorias: "
                + ", ".join(missing)
                + ". Copie .env.example a .env y configure los valores."
            )
            print(f"ERROR: {msg}", file=sys.stderr)
            raise SystemExit(msg)

        secret = os.getenv("SECRET_KEY", "")
        if len(secret) < 16:
            msg = "SECRET_KEY debe tener al menos 16 caracteres."
            print(f"ERROR: {msg}", file=sys.stderr)
            raise SystemExit(msg)

        db_url = os.getenv("DATABASE_URL", "")
        if "sqlite" in db_url.lower():
            msg = "DATABASE_URL no debe apuntar a SQLite en produccion. Use PostgreSQL."
            print(f"ERROR: {msg}", file=sys.stderr)
            raise SystemExit(msg)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL")
    ADMIN_PASSWORD_HASH = "pbkdf2:sha256:600000$test_salt$test_hash"
    HARVEST_TIMEZONE = ZoneInfo("America/Chihuahua")
