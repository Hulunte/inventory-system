import pytest
from decimal import Decimal

from app.models.worker import Worker
from app.models.harvest_entry import HarvestEntry
from app.extensions import db
from sqlalchemy.exc import IntegrityError


class TestWorkerModel:
    def test_create_worker(self, db_session):
        worker = Worker(barcode="W001", name="Juan Perez")
        db_session.add(worker)
        db_session.commit()

        assert worker.id is not None
        assert worker.barcode == "W001"
        assert worker.name == "Juan Perez"
        assert worker.active is True

    def test_find_worker_by_barcode(self, db_session):
        worker = Worker(barcode="W002", name="Maria Garcia")
        db_session.add(worker)
        db_session.commit()

        found = Worker.query.filter_by(barcode="W002", active=True).first()
        assert found is not None
        assert found.name == "Maria Garcia"

    def test_worker_not_found(self, db_session):
        found = Worker.query.filter_by(barcode="NONEXISTENT", active=True).first()
        assert found is None


class TestHarvestEntryModel:
    def test_register_harvest_entry(self, db_session):
        worker = Worker(barcode="W003", name="Carlos Lopez")
        db_session.add(worker)
        db_session.commit()

        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("5.250"))
        db_session.add(entry)
        db_session.commit()

        assert entry.id is not None
        assert entry.weight_kg == Decimal("5.250")
        assert entry.worker_id == worker.id

    def test_accumulate_daily_entries(self, db_session):
        worker = Worker(barcode="W004", name="Ana Torres")
        db_session.add(worker)
        db_session.commit()

        entries = [
            HarvestEntry(worker_id=worker.id, weight_kg=Decimal("5.000")),
            HarvestEntry(worker_id=worker.id, weight_kg=Decimal("6.000")),
            HarvestEntry(worker_id=worker.id, weight_kg=Decimal("4.500")),
        ]
        db_session.add_all(entries)
        db_session.commit()

        total = (
            db_session.query(db.func.sum(HarvestEntry.weight_kg))
            .filter(HarvestEntry.worker_id == worker.id)
            .scalar()
        )
        assert total == Decimal("15.500")

    def test_reject_zero_weight(self, db_session):
        worker = Worker(barcode="W005", name="Pedro Ruiz")
        db_session.add(worker)
        db_session.commit()

        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("0.000"))
        db_session.add(entry)

        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_reject_negative_weight(self, db_session):
        worker = Worker(barcode="W006", name="Laura Diaz")
        db_session.add(worker)
        db_session.commit()

        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("-5.000"))
        db_session.add(entry)

        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestHarvestEndpoints:
    def test_get_worker_by_barcode_endpoint(self, client, db_session):
        worker = Worker(barcode="W007", name="Roberto Sanchez")
        db_session.add(worker)
        db_session.commit()

        response = client.get("/api/workers/W007")
        assert response.status_code == 200
        data = response.get_json()
        assert data["barcode"] == "W007"
        assert data["name"] == "Roberto Sanchez"

    def test_worker_not_found_endpoint(self, client, db_session):
        response = client.get("/api/workers/NONEXISTENT")
        assert response.status_code == 404

    def test_inactive_worker_returns_404(self, client, db_session):
        worker = Worker(barcode="W100", name="Inactive Worker")
        worker.active = False
        db_session.add(worker)
        db_session.commit()

        response = client.get("/api/workers/W100")
        assert response.status_code == 404

    def test_list_workers_endpoint_removed(self, client):
        response = client.get("/api/workers")
        assert response.status_code == 404

    def test_create_worker_endpoint_removed(self, client):
        response = client.post(
            "/api/workers",
            json={"barcode": "W999", "name": "Should Not Work"},
        )
        assert response.status_code == 404

    def test_register_harvest_endpoint(self, client, db_session):
        worker = Worker(barcode="W008", name="Sofia Martin")
        db_session.add(worker)
        db_session.commit()

        response = client.post(
            "/api/harvest/entries",
            json={"barcode": "W008", "weight_kg": 7.250},
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["weight_kg"] == "7.250"
        assert data["worker"]["barcode"] == "W008"
        assert "daily_total" in data

    def test_register_harvest_invalid_weight(self, client, db_session):
        worker = Worker(barcode="W009", name="Diego Hernandez")
        db_session.add(worker)
        db_session.commit()

        response_zero = client.post(
            "/api/harvest/entries",
            json={"barcode": "W009", "weight_kg": 0},
        )
        assert response_zero.status_code == 400

        response_neg = client.post(
            "/api/harvest/entries",
            json={"barcode": "W009", "weight_kg": -3},
        )
        assert response_neg.status_code == 400

    def test_get_daily_total_endpoint(self, client, db_session):
        worker = Worker(barcode="W010", name="Elena Vargas")
        db_session.add(worker)
        db_session.commit()

        client.post(
            "/api/harvest/entries",
            json={"barcode": "W010", "weight_kg": 5.000},
        )
        client.post(
            "/api/harvest/entries",
            json={"barcode": "W010", "weight_kg": 3.500},
        )

        response = client.get("/api/harvest/daily/W010")
        assert response.status_code == 200
        data = response.get_json()
        assert data["daily_total"] == "8.500"
        assert data["worker"]["barcode"] == "W010"
