import os
from datetime import timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
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


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL")
    ADMIN_PASSWORD_HASH = "pbkdf2:sha256:600000$test_salt$test_hash"
    HARVEST_TIMEZONE = ZoneInfo("America/Chihuahua")
