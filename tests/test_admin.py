import pytest
from decimal import Decimal

from app.models.worker import Worker
from app.models.harvest_entry import HarvestEntry
from app.extensions import db
from app.services.worker_service import (
    search_workers,
    get_worker_by_id,
    deactivate_worker,
    activate_worker,
)


class TestWorkerService:
    def test_search_workers_by_name(self, db_session):
        w1 = Worker(barcode="A001", name="Juan Perez")
        w2 = Worker(barcode="A002", name="Maria Garcia")
        db_session.add_all([w1, w2])
        db_session.commit()

        results = search_workers("Juan")
        assert len(results) == 1
        assert results[0].name == "Juan Perez"

    def test_search_workers_by_barcode(self, db_session):
        w1 = Worker(barcode="BC001", name="Pedro Lopez")
        w2 = Worker(barcode="BC002", name="Ana Ruiz")
        db_session.add_all([w1, w2])
        db_session.commit()

        results = search_workers("BC001")
        assert len(results) == 1
        assert results[0].barcode == "BC001"

    def test_search_workers_case_insensitive(self, db_session):
        worker = Worker(barcode="CI001", name="Carlos Mendez")
        db_session.add(worker)
        db_session.commit()

        results = search_workers("carlos")
        assert len(results) == 1
        assert results[0].name == "Carlos Mendez"

    def test_search_workers_partial_match(self, db_session):
        w1 = Worker(barcode="PM001", name="Roberto Sanchez")
        w2 = Worker(barcode="PM002", name="Roberto Diaz")
        w3 = Worker(barcode="PM003", name="Laura Gomez")
        db_session.add_all([w1, w2, w3])
        db_session.commit()

        results = search_workers("Roberto")
        assert len(results) == 2

    def test_search_workers_no_results(self, db_session):
        worker = Worker(barcode="NR001", name="Pedro Perez")
        db_session.add(worker)
        db_session.commit()

        results = search_workers("ZZZZ")
        assert len(results) == 0

    def test_search_workers_includes_inactive(self, db_session):
        w1 = Worker(barcode="IA001", name="Active Worker", active=True)
        w2 = Worker(barcode="IA002", name="Inactive Worker", active=False)
        db_session.add_all([w1, w2])
        db_session.commit()

        results = search_workers()
        barcodes = [w.barcode for w in results]
        assert "IA001" in barcodes
        assert "IA002" in barcodes

    def test_get_worker_by_id_found(self, db_session):
        worker = Worker(barcode="ID001", name="Test Worker")
        db_session.add(worker)
        db_session.commit()

        found = get_worker_by_id(worker.id)
        assert found is not None
        assert found.barcode == "ID001"

    def test_get_worker_by_id_not_found(self, db_session):
        found = get_worker_by_id(99999)
        assert found is None

    def test_deactivate_worker(self, db_session):
        worker = Worker(barcode="DA001", name="Deactivate Me")
        db_session.add(worker)
        db_session.commit()

        result = deactivate_worker(worker.id)
        assert result.active is False

    def test_activate_worker(self, db_session):
        worker = Worker(barcode="AC001", name="Activate Me", active=False)
        db_session.add(worker)
        db_session.commit()

        result = activate_worker(worker.id)
        assert result.active is True

    def test_deactivate_nonexistent(self, db_session):
        result = deactivate_worker(99999)
        assert result is None

    def test_activate_nonexistent(self, db_session):
        result = activate_worker(99999)
        assert result is None


class TestInactiveWorkerHarvest:
    def test_inactive_worker_cannot_register_harvest(self, db_session):
        worker = Worker(barcode="IH001", name="Inactive Harvester", active=False)
        db_session.add(worker)
        db_session.commit()

        from app.services.harvest_service import register_harvest

        entry, daily_total = register_harvest("IH001", Decimal("5.000"))
        assert entry is None
        assert daily_total is None

    def test_inactive_worker_not_found_by_barcode(self, db_session):
        worker = Worker(barcode="IH002", name="Inactive Lookup", active=False)
        db_session.add(worker)
        db_session.commit()

        from app.services.harvest_service import get_worker_by_barcode

        found = get_worker_by_barcode("IH002")
        assert found is None


class TestAdminEndpoints:
    def test_list_workers(self, admin_client, db_session):
        w1 = Worker(barcode="LW001", name="Alpha Worker")
        w2 = Worker(barcode="LW002", name="Beta Worker")
        db_session.add_all([w1, w2])
        db_session.commit()

        response = admin_client.get("/api/admin/workers")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) >= 2

    def test_list_workers_includes_inactive(self, admin_client, db_session):
        w1 = Worker(barcode="LW003", name="Active One", active=True)
        w2 = Worker(barcode="LW004", name="Inactive One", active=False)
        db_session.add_all([w1, w2])
        db_session.commit()

        response = admin_client.get("/api/admin/workers")
        data = response.get_json()
        names = [w["name"] for w in data]
        assert "Active One" in names
        assert "Inactive One" in names

    def test_search_workers_endpoint(self, admin_client, db_session):
        worker = Worker(barcode="SW001", name="Searchable Person")
        db_session.add(worker)
        db_session.commit()

        response = admin_client.get("/api/admin/workers?q=Searchable")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "Searchable Person"

    def test_get_worker_by_id_endpoint(self, admin_client, db_session):
        worker = Worker(barcode="GW001", name="Get By ID")
        db_session.add(worker)
        db_session.commit()

        response = admin_client.get(f"/api/admin/workers/{worker.id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["barcode"] == "GW001"
        assert data["name"] == "Get By ID"

    def test_get_worker_by_id_not_found_endpoint(self, admin_client, db_session):
        response = admin_client.get("/api/admin/workers/99999")
        assert response.status_code == 404

    def test_create_worker_endpoint(self, admin_client, db_session):
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.post(
            "/api/admin/workers",
            json={"name": "New Worker", "barcode": "CW001"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "New Worker"
        assert data["barcode"] == "CW001"
        assert data["active"] is True

    def test_create_worker_empty_name(self, admin_client, db_session):
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.post(
            "/api/admin/workers",
            json={"name": "", "barcode": "EN001"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 400

    def test_create_worker_empty_barcode(self, admin_client, db_session):
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.post(
            "/api/admin/workers",
            json={"name": "No Barcode", "barcode": ""},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 400

    def test_create_worker_whitespace_only(self, admin_client, db_session):
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.post(
            "/api/admin/workers",
            json={"name": "   ", "barcode": "   "},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 400

    def test_create_worker_duplicate_barcode(self, admin_client, db_session):
        worker = Worker(barcode="DU001", name="Existing")
        db_session.add(worker)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.post(
            "/api/admin/workers",
            json={"name": "Duplicate", "barcode": "DU001"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 409

    def test_deactivate_worker_endpoint(self, admin_client, db_session):
        worker = Worker(barcode="DE001", name="Deactivate Endpoint")
        db_session.add(worker)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/workers/{worker.id}/deactivate",
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["active"] is False

    def test_activate_worker_endpoint(self, admin_client, db_session):
        worker = Worker(barcode="AE001", name="Activate Endpoint", active=False)
        db_session.add(worker)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/workers/{worker.id}/activate",
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["active"] is True

    def test_deactivate_nonexistent_endpoint(self, admin_client, db_session):
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            "/api/admin/workers/99999/deactivate",
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 404

    def test_activate_nonexistent_endpoint(self, admin_client, db_session):
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            "/api/admin/workers/99999/activate",
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 404

    def test_inactive_worker_cannot_register_harvest_endpoint(self, admin_client, db_session):
        worker = Worker(barcode="IH003", name="Inactive Harvest Endpoint", active=False)
        db_session.add(worker)
        db_session.commit()

        response = admin_client.post(
            "/api/harvest/entries",
            json={"barcode": "IH003", "weight_kg": 5.0},
        )
        assert response.status_code == 404
