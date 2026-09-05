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


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL")
    ADMIN_PASSWORD_HASH = "pbkdf2:sha256:600000$test_salt$test_hash"
    HARVEST_TIMEZONE = ZoneInfo("America/Chihuahua")
