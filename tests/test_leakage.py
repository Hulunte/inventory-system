import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.models.harvest_entry import HarvestEntry
from app.models.worker import Worker
from tests.conftest import make_worker


class TestLeakageTestA:
    created_barcode = None

    def test_create_worker_and_entry(self, db_session, app):
        with app.app_context():
            w = make_worker(db_session, name="Leakage Test Worker A")
            TestLeakageTestA.created_barcode = w.barcode

            e = HarvestEntry(
                worker_id=w.id,
                weight_kg=Decimal("99.999"),
                created_at=datetime.now(timezone.utc),
            )
            db_session.add(e)
            db_session.flush()


class TestLeakageTestB:
    def test_worker_from_A_should_not_exist(self, db_session, app):
        with app.app_context():
            barcode = TestLeakageTestA.created_barcode
            w = Worker.query.filter_by(barcode=barcode).first()
            assert w is None, f"DATA LEAKAGE CONFIRMED: Worker '{barcode}' found."

    def test_entry_from_A_should_not_exist(self, db_session, app):
        with app.app_context():
            barcode = TestLeakageTestA.created_barcode
            w = Worker.query.filter_by(barcode=barcode).first()
            assert w is None
