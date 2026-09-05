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
from app.models.worker import Worker
from app.models.worker_assignment import WorkerAssignment
from config import TestConfig

import flask_sqlalchemy.session as _fss_session
import sqlalchemy as _sa
import sqlalchemy.exc as _sa_exc
import sqlalchemy.orm as _sa_orm

_original_fss_get_bind = _fss_session.Session.get_bind


def _patched_get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
    """Respect explicit bind from configure(), needed for test isolation.

    Flask-SQLAlchemy's get_bind() resolves to the engine via
    ``engines[None]`` and also checks clause/mapper metadata, ignoring
    any bind set via session.configure().  This patch checks the
    Session's bind attribute (set by configure(bind=...)) FIRST so
    that test fixtures can bind db.session to a Connection with
    join_transaction_mode="create_savepoint" and all ORM + Core
    operations (including ``session.execute(Table.delete())``) go
    through that connection's transaction.
    """
    if bind is not None:
        return bind

    session_bind = self.bind
    if session_bind is not None:
        return session_bind

    engines = self._db.engines

    if mapper is not None:
        try:
            mapper = _sa.inspect(mapper)
        except _sa_exc.NoInspectionAvailable as e:
            if isinstance(mapper, type):
                raise _sa_orm.exc.UnmappedClassError(mapper) from e
            raise

        engine = _fss_session._clause_to_engine(mapper.local_table, engines)

        if engine is not None:
            return engine

    if clause is not None:
        engine = _fss_session._clause_to_engine(clause, engines)

        if engine is not None:
            return engine

    if None in engines:
        return engines[None]

    return _original_fss_get_bind(
        self, mapper=mapper, clause=clause, bind=bind, **kwargs
    )


_fss_session.Session.get_bind = _patched_get_bind


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
def admin_client(app, db_session):
    from werkzeug.security import generate_password_hash

    app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("test-password-123")

    client = app.test_client()

    session_response = client.get("/api/admin/session")
    csrf_token = session_response.get_json()["csrf_token"]

    client.post(
        "/api/admin/login",
        json={"password": "test-password-123"},
        headers={"X-CSRF-Token": csrf_token},
    )

    yield client


@pytest.fixture(scope="function")
def db_session(app):
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()

        _db.session.configure(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )
        _db.session.remove()

        yield _db.session

        _db.session.close()
        transaction.rollback()
        connection.close()


_slot_counter = 0


def _next_slot():
    global _slot_counter
    _slot_counter += 1
    return (_slot_counter % 150) + 1


def make_worker(db_session, barcode=None, name=None, active=True, slot_number=None):
    if slot_number is None:
        slot_number = _next_slot()
    if barcode is None:
        barcode = f"TRB{slot_number:06d}"
    worker = Worker(barcode=barcode, name=name, slot_number=slot_number, active=active)
    db_session.add(worker)
    db_session.flush()
    return worker


def make_assignment(db_session, worker, person_name=None):
    if person_name is None:
        person_name = worker.name or f"Person {worker.slot_number}"
    assignment = WorkerAssignment(
        worker_id=worker.id,
        person_name=person_name,
    )
    db_session.add(assignment)
    db_session.flush()
    return assignment


def make_worker_with_assignment(db_session, barcode=None, name=None, active=True, slot_number=None, person_name=None):
    worker = make_worker(db_session, barcode, name=name, active=active, slot_number=slot_number)
    assignment = make_assignment(db_session, worker, person_name=person_name or name)
    return worker, assignment
