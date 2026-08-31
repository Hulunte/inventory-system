import os

from dotenv import load_dotenv

load_dotenv()

import pytest
from sqlalchemy.engine import make_url


def _get_database_urls():
    dev_url = os.environ.get("DATABASE_URL")
    test_url = os.environ.get("TEST_DATABASE_URL")
    return dev_url, test_url


def _validate_database_safety():
    dev_url_str, test_url_str = _get_database_urls()

    if not test_url_str:
        raise RuntimeError(
            "TEST_DATABASE_URL is not set. "
            "Tests require a dedicated test database. "
            "Set TEST_DATABASE_URL in your environment or .env file."
        )

    if not dev_url_str:
        raise RuntimeError(
            "DATABASE_URL is not set. " "Cannot validate test database isolation."
        )

    dev_url = make_url(dev_url_str)
    test_url = make_url(test_url_str)

    dev_db = dev_url.database
    test_db = test_url.database

    if "test" not in test_db.lower():
        raise RuntimeError(
            f"TEST_DATABASE_URL database name '{test_db}' does not contain 'test'. "
            "Test databases must have 'test' in their name for safety."
        )

    dev_host = dev_url.host or "localhost"
    test_host = test_url.host or "localhost"
    dev_port = dev_url.port or 5432
    test_port = test_url.port or 5432

    if dev_host == test_host and dev_port == test_port and dev_db == test_db:
        raise RuntimeError(
            f"DATABASE_URL and TEST_DATABASE_URL point to the same database: "
            f"{dev_host}:{dev_port}/{dev_db}. "
            "Tests must use a separate test database to avoid destroying development data."
        )


_validate_database_safety()


from app import create_app
from app.extensions import db as _db
from config import TestConfig


@pytest.fixture(scope="session")
def app():
    app = create_app(config_class=TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture(scope="function")
def db_session(app):
    with app.app_context():
        _db.session.begin_nested()
        yield _db.session
        _db.session.rollback()
