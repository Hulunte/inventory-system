import os
import uuid

from flask_migrate import stamp, upgrade
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app import create_app


MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")


def test_reconciliation_migrates_a_stamped_legacy_postgresql_schema():
    """Exercise the real Alembic chain against an isolated PostgreSQL schema."""
    base_url = make_url(os.environ["TEST_DATABASE_URL"])
    schema = f"phase3_migration_{uuid.uuid4().hex}"
    admin_engine = create_engine(base_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    schema_url = base_url.update_query_dict({"options": f"-csearch_path={schema}"})

    class MigrationConfig:
        TESTING = True
        SECRET_KEY = "phase3-migration-test"
        SQLALCHEMY_DATABASE_URI = schema_url.render_as_string(hide_password=False)
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        ADMIN_PASSWORD_HASH = "test"
        TICKET_PAPER_WIDTH_MM = 80
        TICKET_CHARACTERS_PER_LINE = 48
        TICKET_ENCODING = "cp850"
        TICKET_BUSINESS_NAME = "Test"
        TICKET_FOOTER_TEXT = "Test"

    app = create_app(MigrationConfig)
    try:
        with app.app_context():
            upgrade(directory=MIGRATIONS_DIR, revision="d1e2f3a4b5c6")
            engine = app.extensions["sqlalchemy"].engine
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO products (name, rate_per_kg, active) "
                    "VALUES ('Producto anterior', 2.50, true)"
                ))

            assert "average_sack_weight_kg" not in {
                c["name"] for c in inspect(engine).get_columns("products")
            }

            # Reproduce a database stamped at the former head without its DDL.
            stamp(directory=MIGRATIONS_DIR, revision="e2f3a4b5c6d7")
            with engine.connect() as connection:
                revision_before = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
            assert revision_before == "e2f3a4b5c6d7"

            upgrade(directory=MIGRATIONS_DIR, revision="head")
            assert "average_sack_weight_kg" in {
                c["name"] for c in inspect(engine).get_columns("products")
            }
            assert {
                "registration_type", "sack_count", "average_sack_weight_kg_snapshot", "rate_per_sack_snapshot"
            } <= {c["name"] for c in inspect(engine).get_columns("harvest_entries")}

            with engine.connect() as connection:
                revision_after = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                old_average = connection.execute(text(
                    "SELECT average_sack_weight_kg FROM products "
                    "WHERE name = 'Producto anterior'"
                )).scalar_one()
            assert revision_after == "b5c6d7e8f9a0"
            assert old_average is None
            assert "rate_per_sack" in {c["name"] for c in inspect(engine).get_columns("products")}

    finally:
        with app.app_context():
            app.extensions["sqlalchemy"].session.remove()
            app.extensions["sqlalchemy"].engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def test_reconciliation_is_conditional_and_non_destructive():
    migration = (
        __import__("pathlib").Path(MIGRATIONS_DIR)
        / "versions" / "f3a4b5c6d7e8_reconcile_sack_registration_schema.py"
    ).read_text(encoding="utf-8")
    assert 'if "average_sack_weight_kg" not in product_columns' in migration
    assert 'if "registration_type" not in entry_columns' in migration
    assert 'if "sack_count" not in entry_columns' in migration
    assert 'if "average_sack_weight_kg_snapshot" not in entry_columns' in migration
    assert "def downgrade():" in migration


def test_price_separation_migration_is_reversible_and_does_not_rewrite_rows():
    migration = (
        __import__("pathlib").Path(MIGRATIONS_DIR)
        / "versions" / "b5c6d7e8f9a0_separate_scale_and_sack_pricing.py"
    ).read_text(encoding="utf-8")
    assert "UPDATE harvest_entries" not in migration
    assert "DELETE" not in migration
    assert "registration_type = 'scale'" in migration
    assert "registration_type = 'sacks'" in migration
    assert "def downgrade():" in migration
