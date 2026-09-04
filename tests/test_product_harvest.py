import pytest
from decimal import Decimal, ROUND_HALF_UP

from app.models.worker import Worker
from app.models.product import Product
from app.models.harvest_entry import HarvestEntry
from app.extensions import db
from sqlalchemy.exc import IntegrityError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_worker(db_session, barcode="W100", name="Test Worker"):
    worker = Worker(barcode=barcode, name=name)
    db_session.add(worker)
    db_session.commit()
    return worker


def _create_product(db_session, name="Chile", rate="5.25", active=True):
    product = Product(name=name, rate_per_kg=Decimal(rate), active=active)
    db_session.add(product)
    db_session.commit()
    return product


def _register(client, barcode, weight_kg, product_id):
    return client.post(
        "/api/harvest/entries",
        json={
            "barcode": barcode,
            "weight_kg": weight_kg,
            "product_id": product_id,
        },
    )


# ---------------------------------------------------------------------------
# 1. Model and new constraints
# ---------------------------------------------------------------------------

class TestHarvestEntryProductFields:
    def test_new_columns_nullable_for_legacy(self, db_session):
        worker = _create_worker(db_session)
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("1.000"))
        db_session.add(entry)
        db_session.commit()

        assert entry.product_id is None
        assert entry.product_name_snapshot is None
        assert entry.rate_per_kg_snapshot is None
        assert entry.amount_mxn is None

    def test_new_columns_populated_with_product(self, db_session):
        worker = _create_worker(db_session)
        product = _create_product(db_session)
        entry = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("3.500"),
            product_id=product.id,
            product_name_snapshot=product.name,
            rate_per_kg_snapshot=Decimal("5.25"),
            amount_mxn=Decimal("18.38"),
        )
        db_session.add(entry)
        db_session.commit()

        assert entry.product_id == product.id
        assert entry.product_name_snapshot == "Chile"
        assert entry.rate_per_kg_snapshot == Decimal("5.25")
        assert entry.amount_mxn == Decimal("18.38")

    def test_rate_snapshot_negative_rejected(self, db_session):
        worker = _create_worker(db_session, barcode="W101")
        entry = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("1.000"),
            product_id=1,
            product_name_snapshot="X",
            rate_per_kg_snapshot=Decimal("-1.00"),
            amount_mxn=Decimal("1.00"),
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_amount_negative_rejected(self, db_session):
        worker = _create_worker(db_session, barcode="W102")
        entry = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("1.000"),
            product_id=1,
            product_name_snapshot="X",
            rate_per_kg_snapshot=Decimal("5.00"),
            amount_mxn=Decimal("-5.00"),
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_partial_product_fields_rejected(self, db_session):
        worker = _create_worker(db_session, barcode="W103")
        entry = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("1.000"),
            product_id=1,
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


# ---------------------------------------------------------------------------
# 2. Legacy compatibility
# ---------------------------------------------------------------------------

class TestLegacyMovements:
    def test_legacy_entries_have_null_product_fields(self, db_session):
        worker = _create_worker(db_session, barcode="W200")
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("2.000"))
        db_session.add(entry)
        db_session.commit()

        loaded = db.session.get(HarvestEntry, entry.id)
        assert loaded.product_id is None
        assert loaded.product_name_snapshot is None
        assert loaded.rate_per_kg_snapshot is None
        assert loaded.amount_mxn is None

    def test_list_entries_includes_null_product_fields(self, client, db_session):
        worker = _create_worker(db_session, barcode="W201")
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("2.000"))
        db_session.add(entry)
        db_session.commit()

        resp = client.get("/api/harvest/entries")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["product_id"] is None
        assert data[0]["product_name"] is None
        assert data[0]["rate_per_kg"] is None
        assert data[0]["amount_mxn"] is None


# ---------------------------------------------------------------------------
# 3. Creation with active product
# ---------------------------------------------------------------------------

class TestRegisterWithProduct:
    def test_successful_registration(self, client, db_session):
        worker = _create_worker(db_session, barcode="W300")
        product = _create_product(db_session)

        resp = _register(client, "W300", 5.000, product.id)
        assert resp.status_code == 201

        data = resp.get_json()
        assert data["product_id"] == product.id
        assert data["product_name"] == "Chile"
        assert data["rate_per_kg"] == "5.25"
        assert data["amount_mxn"] == "26.25"

    def test_worker_not_found(self, client, db_session):
        product = _create_product(db_session)
        resp = _register(client, "NONEXISTENT", 5.000, product.id)
        assert resp.status_code == 404

    def test_product_not_found(self, client, db_session):
        worker = _create_worker(db_session, barcode="W301")
        resp = _register(client, "W301", 5.000, 99999)
        assert resp.status_code == 404

    def test_inactive_product_rejected(self, client, db_session):
        worker = _create_worker(db_session, barcode="W302")
        product = _create_product(db_session, active=False)
        resp = _register(client, "W302", 5.000, product.id)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 4. Snapshot correctness
# ---------------------------------------------------------------------------

class TestSnapshotCorrectness:
    def test_snapshot_copies_name_and_rate(self, client, db_session):
        worker = _create_worker(db_session, barcode="W400")
        product = _create_product(db_session, name="Cebolla", rate="3.50")

        resp = _register(client, "W400", 2.000, product.id)
        data = resp.get_json()

        assert data["product_name"] == "Cebolla"
        assert data["rate_per_kg"] == "3.50"

    def test_name_price_change_preserves_old_snapshot(self, client, db_session):
        worker = _create_worker(db_session, barcode="W401")
        product = _create_product(db_session, name="Chile", rate="5.00")

        resp1 = _register(client, "W401", 1.000, product.id)
        data1 = resp1.get_json()
        entry_id = data1["id"]

        product.name = "Chile Rojo"
        product.rate_per_kg = Decimal("8.00")
        db_session.commit()

        resp2 = _register(client, "W401", 2.000, product.id)
        data2 = resp2.get_json()

        assert data1["product_name"] == "Chile"
        assert data1["rate_per_kg"] == "5.00"

        assert data2["product_name"] == "Chile Rojo"
        assert data2["rate_per_kg"] == "8.00"

        entry_old = db.session.get(HarvestEntry, entry_id)
        assert entry_old.product_name_snapshot == "Chile"
        assert entry_old.rate_per_kg_snapshot == Decimal("5.00")
        assert entry_old.amount_mxn == Decimal("5.00")


# ---------------------------------------------------------------------------
# 5. Decimal calculation and ROUND_HALF_UP
# ---------------------------------------------------------------------------

class TestAmountCalculation:
    def test_exact_calculation(self, client, db_session):
        worker = _create_worker(db_session, barcode="W500")
        product = _create_product(db_session, rate="3.33")

        resp = _register(client, "W500", 3.000, product.id)
        data = resp.get_json()
        expected = (Decimal("3.33") * Decimal("3.000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert data["amount_mxn"] == str(expected)

    def test_round_half_up_away_from_zero(self, client, db_session):
        worker = _create_worker(db_session, barcode="W501")
        product = _create_product(db_session, rate="1.05")

        resp = _register(client, "W501", 0.001, product.id)
        data = resp.get_json()
        expected = (Decimal("1.05") * Decimal("0.001")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert data["amount_mxn"] == str(expected)

    def test_large_weight(self, client, db_session):
        worker = _create_worker(db_session, barcode="W502")
        product = _create_product(db_session, rate="10.00")

        resp = _register(client, "W502", 999.999, product.id)
        data = resp.get_json()
        expected = (Decimal("10.00") * Decimal("999.999")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert data["amount_mxn"] == str(expected)

    def test_zero_rate(self, client, db_session):
        worker = _create_worker(db_session, barcode="W503")
        product = _create_product(db_session, rate="0.00")

        resp = _register(client, "W503", 5.000, product.id)
        data = resp.get_json()
        assert data["amount_mxn"] == "0.00"


# ---------------------------------------------------------------------------
# 6. product_id validation
# ---------------------------------------------------------------------------

class TestProductIdValidation:
    @pytest.mark.parametrize("bad_id", [
        None,
        "abc",
        1.5,
        True,
        False,
        [],
        {},
    ])
    def test_invalid_product_id_type(self, client, db_session, bad_id):
        worker = _create_worker(db_session, barcode="W600")
        resp = client.post(
            "/api/harvest/entries",
            json={"barcode": "W600", "weight_kg": 5.0, "product_id": bad_id},
        )
        assert resp.status_code == 400

    def test_negative_product_id(self, client, db_session):
        worker = _create_worker(db_session, barcode="W601")
        resp = client.post(
            "/api/harvest/entries",
            json={"barcode": "W601", "weight_kg": 5.0, "product_id": -1},
        )
        assert resp.status_code == 400

    def test_zero_product_id(self, client, db_session):
        worker = _create_worker(db_session, barcode="W602")
        resp = client.post(
            "/api/harvest/entries",
            json={"barcode": "W602", "weight_kg": 5.0, "product_id": 0},
        )
        assert resp.status_code == 400

    def test_missing_product_id(self, client, db_session):
        worker = _create_worker(db_session, barcode="W603")
        resp = client.post(
            "/api/harvest/entries",
            json={"barcode": "W603", "weight_kg": 5.0},
        )
        assert resp.status_code == 400
        assert "product_id" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# 7. No partial data on validation failure
# ---------------------------------------------------------------------------

class TestNoPartialData:
    def test_no_entry_created_on_invalid_product(self, client, db_session):
        worker = _create_worker(db_session, barcode="W700")
        count_before = HarvestEntry.query.count()

        resp = _register(client, "W700", 5.000, 99999)
        assert resp.status_code == 404

        count_after = HarvestEntry.query.count()
        assert count_after == count_before

    def test_no_entry_on_inactive_product(self, client, db_session):
        worker = _create_worker(db_session, barcode="W701")
        product = _create_product(db_session, active=False)
        count_before = HarvestEntry.query.count()

        resp = _register(client, "W701", 5.000, product.id)
        assert resp.status_code == 404

        count_after = HarvestEntry.query.count()
        assert count_after == count_before


# ---------------------------------------------------------------------------
# 8. Public products endpoint
# ---------------------------------------------------------------------------

class TestActiveProductsEndpoint:
    def test_returns_only_active(self, client, db_session):
        _create_product(db_session, name="Chile", active=True)
        _create_product(db_session, name="Inactivo", active=False)

        resp = client.get("/api/products/active")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "Chile"

    def test_ordered_alphabetically(self, client, db_session):
        _create_product(db_session, name="Zanahoria")
        _create_product(db_session, name="Chile")
        _create_product(db_session, name="Alcachofa")

        resp = client.get("/api/products/active")
        data = resp.get_json()
        names = [p["name"] for p in data]
        assert names == ["Alcachofa", "Chile", "Zanahoria"]

    def test_exposes_only_id_name_rate(self, client, db_session):
        _create_product(db_session)

        resp = client.get("/api/products/active")
        data = resp.get_json()
        assert len(data) == 1
        product = data[0]
        assert set(product.keys()) == {"id", "name", "rate_per_kg"}

    def test_no_auth_required(self, client, db_session):
        _create_product(db_session)
        resp = client.get("/api/products/active")
        assert resp.status_code == 200

    def test_empty_when_no_active(self, client, db_session):
        _create_product(db_session, active=False)
        resp = client.get("/api/products/active")
        assert resp.status_code == 200
        assert resp.get_json() == []


# ---------------------------------------------------------------------------
# 9. Existing endpoint regression
# ---------------------------------------------------------------------------

class TestExistingEndpointsRegression:
    def test_register_harvest_still_works_with_product(self, client, db_session):
        worker = _create_worker(db_session, barcode="W900")
        product = _create_product(db_session)

        resp = _register(client, "W900", 7.250, product.id)
        assert resp.status_code == 201
        data = resp.get_json()
        assert "daily_total" in data
        assert "worker" in data

    def test_daily_total_endpoint(self, client, db_session):
        worker = _create_worker(db_session, barcode="W901")
        product = _create_product(db_session)

        _register(client, "W901", 3.000, product.id)
        _register(client, "W901", 2.000, product.id)

        resp = client.get("/api/harvest/daily/W901")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["daily_total"] == "5.000"

    def test_invalid_weight_still_rejected(self, client, db_session):
        worker = _create_worker(db_session, barcode="W902")
        product = _create_product(db_session)

        resp = _register(client, "W902", 0, product.id)
        assert resp.status_code == 400

        resp = _register(client, "W902", -5, product.id)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 10. Reception UI elements
# ---------------------------------------------------------------------------

class TestReceptionUI:
    def test_reception_page_has_product_selector(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert 'id="product-selector"' in html
        assert 'id="product-buttons"' in html

    def test_reception_page_has_aria_pressed_in_js(self, client):
        resp = client.get("/static/js/reception.js")
        js = resp.data.decode()
        assert "aria-pressed" in js

    def test_reception_js_references_selectedProductId(self, client):
        resp = client.get("/static/js/reception.js")
        js = resp.data.decode()
        assert "selectedProductId" in js
        assert "localStorage" in js
        assert "product_id" in js
        assert "escapeHtml" in js
        assert "/api/products/active" in js
