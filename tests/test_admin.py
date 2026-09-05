import pytest
from datetime import date
from decimal import Decimal

from app.models.worker import Worker
from app.models.harvest_entry import HarvestEntry
from app.extensions import db
from app.services.worker_slot_service import (
    search_worker_slots,
    get_worker_slot_by_id,
    deactivate_slot,
    activate_slot,
)


class TestWorkerService:
    def test_search_workers_by_name(self, db_session):
        w1 = Worker(barcode="TRB000001", name="Juan Perez", slot_number=1)
        w2 = Worker(barcode="TRB000002", name="Maria Garcia", slot_number=2)
        db_session.add_all([w1, w2])
        db_session.commit()

        results = search_worker_slots("Juan")
        assert len(results) == 1
        assert results[0].name == "Juan Perez"

    def test_search_workers_by_barcode(self, db_session):
        w1 = Worker(barcode="TRB000003", name="Pedro Lopez", slot_number=3)
        w2 = Worker(barcode="TRB000004", name="Ana Ruiz", slot_number=4)
        db_session.add_all([w1, w2])
        db_session.commit()

        results = search_worker_slots("TRB000003")
        assert len(results) == 1
        assert results[0].barcode == "TRB000003"

    def test_search_workers_case_insensitive(self, db_session):
        worker = Worker(barcode="TRB000005", name="Carlos Mendez", slot_number=5)
        db_session.add(worker)
        db_session.commit()

        results = search_worker_slots("carlos")
        assert len(results) == 1
        assert results[0].name == "Carlos Mendez"

    def test_search_workers_partial_match(self, db_session):
        w1 = Worker(barcode="TRB000006", name="Roberto Sanchez", slot_number=6)
        w2 = Worker(barcode="TRB000007", name="Roberto Diaz", slot_number=7)
        w3 = Worker(barcode="TRB000008", name="Laura Gomez", slot_number=8)
        db_session.add_all([w1, w2, w3])
        db_session.commit()

        results = search_worker_slots("Roberto")
        assert len(results) == 2

    def test_search_workers_no_results(self, db_session):
        worker = Worker(barcode="TRB000009", name="Pedro Perez", slot_number=9)
        db_session.add(worker)
        db_session.commit()

        results = search_worker_slots("ZZZZ")
        assert len(results) == 0

    def test_search_workers_includes_inactive(self, db_session):
        w1 = Worker(barcode="TRB000010", name="Active Worker", active=True, slot_number=10)
        w2 = Worker(barcode="TRB000011", name="Inactive Worker", active=False, slot_number=11)
        db_session.add_all([w1, w2])
        db_session.commit()

        results = search_worker_slots(include_inactive=True)
        barcodes = [w.barcode for w in results]
        assert "TRB000010" in barcodes
        assert "TRB000011" in barcodes

    def test_get_worker_by_id_found(self, db_session):
        worker = Worker(barcode="TRB000012", name="Test Worker", slot_number=12)
        db_session.add(worker)
        db_session.commit()

        found = get_worker_slot_by_id(worker.id)
        assert found is not None
        assert found.barcode == "TRB000012"

    def test_get_worker_by_id_not_found(self, db_session):
        found = get_worker_slot_by_id(99999)
        assert found is None

    def test_deactivate_worker(self, db_session):
        worker = Worker(barcode="TRB000013", name="Deactivate Me", slot_number=13)
        db_session.add(worker)
        db_session.commit()

        result = deactivate_slot(worker.id)
        assert result.active is False

    def test_activate_worker(self, db_session):
        worker = Worker(barcode="TRB000014", name="Activate Me", active=False, slot_number=14)
        db_session.add(worker)
        db_session.commit()

        result = activate_slot(worker.id)
        assert result.active is True

    def test_deactivate_nonexistent(self, db_session):
        result = deactivate_slot(99999)
        assert result is None

    def test_activate_nonexistent(self, db_session):
        result = activate_slot(99999)
        assert result is None


class TestInactiveWorkerHarvest:
    def test_inactive_worker_cannot_register_harvest(self, db_session):
        from decimal import Decimal
        from app.models.product import Product

        worker = Worker(barcode="TRB000015", name="Inactive Harvester", active=False, slot_number=15)
        db_session.add(worker)
        product = Product(name="IHProd", rate_per_kg=Decimal("2.00"))
        db_session.add(product)
        db_session.commit()

        from app.services.harvest_service import register_harvest

        entry, daily_total = register_harvest("TRB000015", Decimal("5.000"), product.id)
        assert entry is None
        assert daily_total is None

    def test_inactive_worker_not_found_by_barcode(self, db_session):
        worker = Worker(barcode="TRB000016", name="Inactive Lookup", active=False, slot_number=16)
        db_session.add(worker)
        db_session.commit()

        from app.services.harvest_service import get_worker_by_barcode

        found = get_worker_by_barcode("TRB000016")
        assert found is None


class TestAdminEndpoints:
    def test_list_workers(self, admin_client, db_session):
        w1 = Worker(barcode="TRB000017", name="Alpha Worker", slot_number=17)
        w2 = Worker(barcode="TRB000018", name="Beta Worker", slot_number=18)
        db_session.add_all([w1, w2])
        db_session.commit()

        response = admin_client.get("/api/admin/worker-slots")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) >= 2

    def test_list_workers_includes_inactive(self, admin_client, db_session):
        w1 = Worker(barcode="TRB000019", name="Active One", active=True, slot_number=19)
        w2 = Worker(barcode="TRB000020", name="Inactive One", active=False, slot_number=20)
        db_session.add_all([w1, w2])
        db_session.commit()

        response = admin_client.get("/api/admin/worker-slots?include_inactive=true")
        data = response.get_json()
        names = [w["name"] for w in data]
        assert "Active One" in names
        assert "Inactive One" in names

    def test_search_workers_endpoint(self, admin_client, db_session):
        worker = Worker(barcode="TRB000021", name="Searchable Person", slot_number=21)
        db_session.add(worker)
        db_session.commit()

        response = admin_client.get("/api/admin/worker-slots?q=Searchable")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "Searchable Person"

    def test_get_worker_by_id_endpoint(self, admin_client, db_session):
        worker = Worker(barcode="TRB000022", name="Get By ID", slot_number=22)
        db_session.add(worker)
        db_session.commit()

        response = admin_client.get(f"/api/admin/worker-slots?q=TRB000022")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["barcode"] == "TRB000022"
        assert data[0]["name"] == "Get By ID"

    def test_get_worker_by_id_not_found_endpoint(self, admin_client, db_session):
        response = admin_client.get("/api/admin/worker-slots?q=NONEXISTENT99999")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 0

    def test_assign_worker_slot_endpoint(self, admin_client, db_session):
        from tests.conftest import make_worker

        worker = make_worker(db_session, barcode="TRB000023", name="New Worker", slot_number=23)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/worker-slots/{worker.id}/assign",
            json={"person_name": "New Worker"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["person_name"] == "New Worker"
        assert data["barcode"] == "TRB000023"
        assert data["active"] is True

    def test_assign_worker_slot_empty_name(self, admin_client, db_session):
        from tests.conftest import make_worker

        worker = make_worker(db_session, barcode="TRB000024", slot_number=24)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/worker-slots/{worker.id}/assign",
            json={"person_name": ""},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 400

    def test_assign_worker_slot_not_found(self, admin_client, db_session):
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            "/api/admin/worker-slots/99999/assign",
            json={"person_name": "No One"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 404

    def test_assign_worker_slot_whitespace_name(self, admin_client, db_session):
        from tests.conftest import make_worker

        worker = make_worker(db_session, barcode="TRB000025", slot_number=25)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/worker-slots/{worker.id}/assign",
            json={"person_name": "   "},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 400

    def test_assign_worker_slot_reassign(self, admin_client, db_session):
        from tests.conftest import make_worker

        worker = make_worker(db_session, barcode="TRB000026", slot_number=26)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]

        response = admin_client.patch(
            f"/api/admin/worker-slots/{worker.id}/assign",
            json={"person_name": "First Person"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200

        response = admin_client.patch(
            f"/api/admin/worker-slots/{worker.id}/assign",
            json={"person_name": "Second Person"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["person_name"] == "Second Person"

    def test_deactivate_worker_endpoint(self, admin_client, db_session):
        worker = Worker(barcode="TRB000027", name="Deactivate Endpoint", slot_number=27)
        db_session.add(worker)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/worker-slots/{worker.id}/deactivate",
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["active"] is False

    def test_activate_worker_endpoint(self, admin_client, db_session):
        worker = Worker(barcode="TRB000028", name="Activate Endpoint", active=False, slot_number=28)
        db_session.add(worker)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/worker-slots/{worker.id}/activate",
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["active"] is True

    def test_deactivate_nonexistent_endpoint(self, admin_client, db_session):
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            "/api/admin/worker-slots/99999/deactivate",
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 404

    def test_activate_nonexistent_endpoint(self, admin_client, db_session):
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            "/api/admin/worker-slots/99999/activate",
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 404

    def test_inactive_worker_cannot_register_harvest_endpoint(self, admin_client, db_session):
        from decimal import Decimal
        from app.models.product import Product

        worker = Worker(barcode="TRB000029", name="Inactive Harvest Endpoint", active=False, slot_number=29)
        db_session.add(worker)
        product = Product(name="IHProd3", rate_per_kg=Decimal("2.00"))
        db_session.add(product)
        db_session.commit()

        response = admin_client.post(
            "/api/harvest/entries",
            json={
                "barcode": "TRB000029",
                "weight_kg": 5.0,
                "product_id": product.id,
            },
        )
        assert response.status_code == 404


class TestAdminPageOperationalToday:
    def test_admin_page_operational_today(self, admin_client, monkeypatch):
        monkeypatch.setattr("app.routes.views._operational_today", lambda: date(2026, 6, 17))
        response = admin_client.get("/admin")
        assert response.status_code == 200
        html = response.data.decode()
        assert 'ADMIN_CONFIG' in html
        assert 'operationalToday: "2026-06-17"' in html


class TestProductsPage:
    def test_products_page_redirects_without_session(self, client):
        response = client.get("/admin/products", follow_redirects=False)
        assert response.status_code == 302
        assert "/admin/login" in response.headers["Location"]

    def test_products_page_200_for_admin(self, admin_client):
        response = admin_client.get("/admin/products")
        assert response.status_code == 200

    def test_products_page_contains_form(self, admin_client):
        response = admin_client.get("/admin/products")
        html = response.data.decode()
        assert 'id="product-form"' in html
        assert 'id="product-name"' in html
        assert 'id="product-rate"' in html
        assert 'id="product-submit"' in html

    def test_products_page_contains_search(self, admin_client):
        response = admin_client.get("/admin/products")
        html = response.data.decode()
        assert 'id="product-search-input"' in html

    def test_products_page_contains_list(self, admin_client):
        response = admin_client.get("/admin/products")
        html = response.data.decode()
        assert 'id="product-list"' in html

    def test_products_page_contains_modal(self, admin_client):
        response = admin_client.get("/admin/products")
        html = response.data.decode()
        assert 'id="edit-product-modal"' in html
        assert 'id="edit-product-form"' in html

    def test_products_page_loads_products_js(self, admin_client):
        response = admin_client.get("/admin/products")
        html = response.data.decode()
        assert 'products.js' in html

    def test_products_page_has_nav_link_to_admin(self, admin_client):
        response = admin_client.get("/admin/products")
        html = response.data.decode()
        assert '/admin' in html

    def test_products_page_no_product_section_in_admin(self, admin_client):
        response = admin_client.get("/admin")
        html = response.data.decode()
        assert 'id="products-section"' not in html
        assert 'id="product-form"' not in html
        assert 'id="edit-product-modal"' not in html

    def test_admin_page_has_products_nav_link(self, admin_client):
        response = admin_client.get("/admin")
        html = response.data.decode()
        assert '/admin/products' in html
        assert 'Productos' in html


class TestAdminJsNoProductRefs:
    def test_admin_js_has_no_product_refs(self):
        import os
        js_path = os.path.join(os.path.dirname(__file__), "..", "app", "static", "js", "admin.js")
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "product-form" not in content
        assert "product-name" not in content
        assert "product-rate" not in content
        assert "product-submit" not in content
        assert "product-search-input" not in content
        assert "product-list" not in content
        assert "edit-product-modal" not in content
        assert "edit-product-form" not in content
        assert "loadProducts" not in content
        assert "renderProduct" not in content
        assert "productsById" not in content
