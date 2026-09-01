import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.models.worker import Worker
from app.models.harvest_entry import HarvestEntry


class TestLeakageTestA:
    def test_create_worker_and_entry(self, db_session, app):
        with app.app_context():
            w = Worker(barcode="LEAK-A-001", name="Leakage Test Worker A")
            db_session.add(w)
            db_session.flush()

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
            w = Worker.query.filter_by(barcode="LEAK-A-001").first()
            assert w is None, "DATA LEAKAGE CONFIRMED: Worker 'LEAK-A-001' found."

    def test_entry_from_A_should_not_exist(self, db_session, app):
        with app.app_context():
            w = Worker.query.filter_by(barcode="LEAK-A-001").first()
            assert w is None
