import pytest
from decimal import Decimal, ROUND_HALF_UP

from app.models.product import Product
from app.models.harvest_entry import HarvestEntry
from app.extensions import db
from app.exceptions import ProductUnavailableError
from sqlalchemy.exc import IntegrityError
from tests.conftest import make_worker, make_worker_with_assignment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
        worker = make_worker(db_session)
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("1.000"))
        db_session.add(entry)
        db_session.commit()

        assert entry.product_id is None
        assert entry.product_name_snapshot is None
        assert entry.rate_per_kg_snapshot is None
        assert entry.amount_mxn is None

    def test_new_columns_populated_with_product(self, db_session):
        worker = make_worker(db_session)
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
        worker = make_worker(db_session)
        product = _create_product(db_session, name="NegRate")
        entry = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("1.000"),
            product_id=product.id,
            product_name_snapshot="NegRate",
            rate_per_kg_snapshot=Decimal("-1.00"),
            amount_mxn=Decimal("1.00"),
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_amount_negative_rejected(self, db_session):
        worker = make_worker(db_session)
        product = _create_product(db_session, name="NegAmt")
        entry = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("1.000"),
            product_id=product.id,
            product_name_snapshot="NegAmt",
            rate_per_kg_snapshot=Decimal("5.00"),
            amount_mxn=Decimal("-5.00"),
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_partial_product_fields_rejected(self, db_session):
        worker = make_worker(db_session)
        product = _create_product(db_session, name="PartialFields")
        entry = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("1.000"),
            product_id=product.id,
        )
        db_session.add(entry)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_fk_declares_restrict(self):
        from sqlalchemy import inspect
        mapper = inspect(HarvestEntry)
        table = mapper.local_table
        for fk in table.foreign_keys:
            if fk.column.table.name == "products":
                assert fk.ondelete == "RESTRICT"
                return
        pytest.fail("No FK to products found")


# ---------------------------------------------------------------------------
# 2. Legacy compatibility
# ---------------------------------------------------------------------------

class TestLegacyMovements:
    def test_legacy_entries_have_null_product_fields(self, db_session):
        worker = make_worker(db_session)
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("2.000"))
        db_session.add(entry)
        db_session.commit()

        loaded = db.session.get(HarvestEntry, entry.id)
        assert loaded.product_id is None
        assert loaded.product_name_snapshot is None
        assert loaded.rate_per_kg_snapshot is None
        assert loaded.amount_mxn is None

    def test_list_entries_includes_null_product_fields(self, client, db_session):
        worker = make_worker(db_session)
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
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session)

        resp = _register(client, worker.barcode, 5.000, product.id)
        assert resp.status_code == 201

        data = resp.get_json()
        assert data["product_id"] == product.id
        assert data["product_name"] == "Chile"
        assert data["rate_per_kg"] == "5.25"
        assert data["amount_mxn"] == "26.25"

    def test_worker_not_found_returns_404(self, client, db_session):
        product = _create_product(db_session)
        resp = _register(client, "NONEXISTENT", 5.000, product.id)
        assert resp.status_code == 404
        assert "Trabajador" in resp.get_json()["error"]

    def test_product_not_found_returns_409(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        resp = _register(client, worker.barcode, 5.000, 99999)
        assert resp.status_code == 409
        data = resp.get_json()
        assert data["code"] == "product_unavailable"

    def test_inactive_product_returns_409(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, active=False)
        resp = _register(client, worker.barcode, 5.000, product.id)
        assert resp.status_code == 409
        data = resp.get_json()
        assert data["code"] == "product_unavailable"


# ---------------------------------------------------------------------------
# 4. Snapshot correctness
# ---------------------------------------------------------------------------

class TestSnapshotCorrectness:
    def test_snapshot_copies_name_and_rate(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="Cebolla", rate="3.50")

        resp = _register(client, worker.barcode, 2.000, product.id)
        data = resp.get_json()

        assert data["product_name"] == "Cebolla"
        assert data["rate_per_kg"] == "3.50"

    def test_name_price_change_preserves_old_snapshot(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="Chile", rate="5.00")

        resp1 = _register(client, worker.barcode, 1.000, product.id)
        data1 = resp1.get_json()
        entry_id = data1["id"]

        product.name = "Chile Rojo"
        product.rate_per_kg = Decimal("8.00")
        db_session.commit()

        resp2 = _register(client, worker.barcode, 2.000, product.id)
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
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, rate="3.33")

        resp = _register(client, worker.barcode, 3.000, product.id)
        data = resp.get_json()
        assert data["amount_mxn"] == "9.99"

    def test_round_half_up_exact_half_cent(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, rate="5.00")

        resp = _register(client, worker.barcode, 0.001, product.id)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["amount_mxn"] == "0.01"

    def test_large_weight(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, rate="10.00")

        resp = _register(client, worker.barcode, 999.999, product.id)
        data = resp.get_json()
        assert data["amount_mxn"] == "9999.99"

    def test_zero_rate(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, rate="0.00")

        resp = _register(client, worker.barcode, 5.000, product.id)
        data = resp.get_json()
        assert data["amount_mxn"] == "0.00"

    def test_price_has_exactly_two_decimals(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, rate="3.00")

        resp = _register(client, worker.barcode, 2.000, product.id)
        data = resp.get_json()
        assert data["rate_per_kg"] == "3.00"
        parts = data["amount_mxn"].split(".")
        assert len(parts) == 2 and len(parts[1]) == 2

    def test_success_returns_backend_applied_price(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, rate="7.50")

        resp = _register(client, worker.barcode, 1.000, product.id)
        data = resp.get_json()
        assert data["rate_per_kg"] == "7.50"
        assert data["amount_mxn"] == "7.50"


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
        worker, _ = make_worker_with_assignment(db_session)
        resp = client.post(
            "/api/harvest/entries",
            json={"barcode": worker.barcode, "weight_kg": 5.0, "product_id": bad_id},
        )
        assert resp.status_code == 400

    def test_negative_product_id(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        resp = client.post(
            "/api/harvest/entries",
            json={"barcode": worker.barcode, "weight_kg": 5.0, "product_id": -1},
        )
        assert resp.status_code == 400

    def test_zero_product_id(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        resp = client.post(
            "/api/harvest/entries",
            json={"barcode": worker.barcode, "weight_kg": 5.0, "product_id": 0},
        )
        assert resp.status_code == 400

    def test_missing_product_id(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        resp = client.post(
            "/api/harvest/entries",
            json={"barcode": worker.barcode, "weight_kg": 5.0},
        )
        assert resp.status_code == 400
        assert "product_id" in resp.get_json()["error"]

    def test_service_raises_valueerror_for_bool(self, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        from app.services.harvest_service import register_harvest
        with pytest.raises(ValueError, match="product_id"):
            register_harvest(worker.barcode, Decimal("5.000"), True)

    def test_service_raises_valueerror_for_none(self, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        from app.services.harvest_service import register_harvest
        with pytest.raises(ValueError, match="product_id"):
            register_harvest(worker.barcode, Decimal("5.000"), None)

    def test_service_raises_valueerror_for_string(self, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        from app.services.harvest_service import register_harvest
        with pytest.raises(ValueError, match="product_id"):
            register_harvest(worker.barcode, Decimal("5.000"), "abc")

    def test_service_raises_valueerror_for_zero(self, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        from app.services.harvest_service import register_harvest
        with pytest.raises(ValueError, match="product_id"):
            register_harvest(worker.barcode, Decimal("5.000"), 0)

    def test_service_raises_valueerror_for_negative(self, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        from app.services.harvest_service import register_harvest
        with pytest.raises(ValueError, match="product_id"):
            register_harvest(worker.barcode, Decimal("5.000"), -1)


# ---------------------------------------------------------------------------
# 7. No partial data on validation failure
# ---------------------------------------------------------------------------

class TestNoPartialData:
    def test_no_entry_created_on_invalid_product(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        count_before = HarvestEntry.query.count()

        resp = _register(client, worker.barcode, 5.000, 99999)
        assert resp.status_code == 409

        count_after = HarvestEntry.query.count()
        assert count_after == count_before

    def test_no_entry_on_inactive_product(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, active=False)
        count_before = HarvestEntry.query.count()

        resp = _register(client, worker.barcode, 5.000, product.id)
        assert resp.status_code == 409

        count_after = HarvestEntry.query.count()
        assert count_after == count_before

    def test_no_entry_on_invalid_weight(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="W702Prod")
        count_before = HarvestEntry.query.count()

        resp = _register(client, worker.barcode, 0, product.id)
        assert resp.status_code == 400

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

    def test_price_has_two_decimals(self, client, db_session):
        _create_product(db_session, rate="3.00")
        resp = client.get("/api/products/active")
        data = resp.get_json()
        assert data[0]["rate_per_kg"] == "3.00"


# ---------------------------------------------------------------------------
# 9. Existing endpoint regression
# ---------------------------------------------------------------------------

class TestExistingEndpointsRegression:
    def test_register_harvest_still_works_with_product(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session)

        resp = _register(client, worker.barcode, 7.250, product.id)
        assert resp.status_code == 201
        data = resp.get_json()
        assert "daily_total" in data
        assert "worker" in data

    def test_daily_total_endpoint(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session)

        _register(client, worker.barcode, 3.000, product.id)
        _register(client, worker.barcode, 2.000, product.id)

        resp = client.get(f"/api/harvest/daily/{worker.barcode}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["daily_total"] == "5.000"

    def test_invalid_weight_still_rejected(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="W902Prod")

        resp = _register(client, worker.barcode, 0, product.id)
        assert resp.status_code == 400

        resp = _register(client, worker.barcode, -5, product.id)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 10. JSON and body validation
# ---------------------------------------------------------------------------

class TestJsonValidation:
    def test_malformed_json_returns_400(self, client):
        resp = client.post(
            "/api/harvest/entries",
            data="not json",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_non_object_json_returns_400(self, client):
        resp = client.post(
            "/api/harvest/entries",
            json=[1, 2, 3],
        )
        assert resp.status_code == 400

    def test_string_body_returns_400(self, client):
        resp = client.post(
            "/api/harvest/entries",
            json="string",
        )
        assert resp.status_code == 400

    def test_number_body_returns_400(self, client):
        resp = client.post(
            "/api/harvest/entries",
            json=42,
        )
        assert resp.status_code == 400

    def test_boolean_body_returns_400(self, client):
        resp = client.post(
            "/api/harvest/entries",
            json=True,
        )
        assert resp.status_code == 400

    def test_null_body_returns_400(self, client):
        resp = client.post(
            "/api/harvest/entries",
            json=None,
        )
        assert resp.status_code == 400

    def test_unknown_fields_rejected(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        resp = client.post(
            "/api/harvest/entries",
            json={
                "barcode": worker.barcode,
                "weight_kg": 5.0,
                "product_id": 1,
                "extra_field": "bad",
            },
        )
        assert resp.status_code == 400
        assert "extra_field" in resp.get_json()["error"]

    def test_weight_kg_bool_rejected(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="W801Prod")
        resp = client.post(
            "/api/harvest/entries",
            json={"barcode": worker.barcode, "weight_kg": True, "product_id": product.id},
        )
        assert resp.status_code == 400

    def test_weight_kg_nan_rejected(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="W802Prod")
        resp = client.post(
            "/api/harvest/entries",
            json={"barcode": worker.barcode, "weight_kg": "NaN", "product_id": product.id},
        )
        assert resp.status_code == 400

    def test_weight_kg_infinite_rejected(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="W803Prod")
        resp = client.post(
            "/api/harvest/entries",
            json={"barcode": worker.barcode, "weight_kg": "Infinity", "product_id": product.id},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 11. Weight precision (max 3 decimals)
# ---------------------------------------------------------------------------

class TestWeightPrecision:
    def test_four_decimals_rejected(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="WPP1")
        resp = _register(client, worker.barcode, "1.2345", product.id)
        assert resp.status_code == 400

    def test_no_entry_on_too_many_decimals(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="WPP2")
        count_before = HarvestEntry.query.count()
        resp = _register(client, worker.barcode, "1.2345", product.id)
        assert resp.status_code == 400
        assert HarvestEntry.query.count() == count_before

    def test_three_decimals_accepted(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="WPP3")
        resp = _register(client, worker.barcode, "5.000", product.id)
        assert resp.status_code == 201

    def test_integer_accepted(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="WPP4")
        resp = _register(client, worker.barcode, "5", product.id)
        assert resp.status_code == 201

    def test_one_decimal_accepted(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="WPP5")
        resp = _register(client, worker.barcode, "5.0", product.id)
        assert resp.status_code == 201

    def test_two_decimals_accepted(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="WPP6")
        resp = _register(client, worker.barcode, "5.00", product.id)
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# 12. ProductUnavailableError direct service tests
# ---------------------------------------------------------------------------

class TestProductUnavailableError:
    def test_nonexistent_product_raises_error(self, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        from app.services.harvest_service import register_harvest
        with pytest.raises(ProductUnavailableError):
            register_harvest(worker.barcode, Decimal("5.000"), 99999)

    def test_inactive_product_raises_error(self, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="InactiveP", active=False)
        from app.services.harvest_service import register_harvest
        with pytest.raises(ProductUnavailableError):
            register_harvest(worker.barcode, Decimal("5.000"), product.id)

    def test_worker_not_found_still_returns_none(self, db_session):
        from app.services.harvest_service import register_harvest
        entry, total = register_harvest("NONEXISTENT", Decimal("5.000"), 99999)
        assert entry is None
        assert total is None


# ---------------------------------------------------------------------------
# 13. HTTP endpoint differentiation
# ---------------------------------------------------------------------------

class TestHttpEndpointDifferentiation:
    def test_worker_not_found_404_vs_product_409(self, client, db_session):
        resp_404 = _register(client, "GHOST", 5.000, 1)
        assert resp_404.status_code == 404

        worker, _ = make_worker_with_assignment(db_session)
        resp_409 = _register(client, worker.barcode, 5.000, 99999)
        assert resp_409.status_code == 409

    def test_response_409_contains_product_unavailable_code(
        self, client, db_session
    ):
        worker, _ = make_worker_with_assignment(db_session)
        resp = _register(client, worker.barcode, 5.000, 99999)
        data = resp.get_json()
        assert resp.status_code == 409
        assert data["code"] == "product_unavailable"
        assert "error" in data

    def test_valueerror_returns_400_not_409(self, client, db_session):
        worker, _ = make_worker_with_assignment(db_session)
        resp = _register(client, worker.barcode, 5.000, True)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 14. FOR UPDATE locking (real SQL observation)
# ---------------------------------------------------------------------------

class TestForUpdateLocking:
    def test_for_update_in_executed_sql(self, client, db_session):
        from sqlalchemy import event
        worker, _ = make_worker_with_assignment(db_session)
        product = _create_product(db_session, name="LockTest")

        seen_statements = []

        def _capture(conn, cursor, statement, parameters, context, executemany):
            seen_statements.append(statement)

        event.listen(db.engine, "before_cursor_execute", _capture)
        try:
            resp = _register(client, worker.barcode, 1.000, product.id)
            assert resp.status_code == 201
            for_update_clauses = [
                s for s in seen_statements
                if "FOR UPDATE" in s.upper() and "products" in s.lower()
            ]
            assert len(for_update_clauses) >= 1
        finally:
            event.remove(db.engine, "before_cursor_execute", _capture)


# ---------------------------------------------------------------------------
# 15. Reception UI
# ---------------------------------------------------------------------------

class TestReceptionUI:
    def test_html_structure(self, client):
        resp = client.get("/")
        html = resp.data.decode()
        assert 'id="product-selector"' in html
        assert 'id="product-buttons"' in html
        assert 'id="product-warning"' in html
        assert "hidden" in html

        css_resp = client.get("/static/css/reception.css")
        css = css_resp.data.decode()
        assert "[hidden]" in css
        assert "display: none !important" in css

    def test_accessible_selection_and_persistence(self, client):
        resp = client.get("/static/js/reception.js")
        js = resp.data.decode()
        assert "aria-pressed" in js
        assert "inventory.selectedProductId" in js
        assert r"/^\d+$/.test(raw)" in js

    def test_payload_string_product_id_no_number_conversion(self, client):
        resp = client.get("/static/js/reception.js")
        js = resp.data.decode()
        assert "product_id: selectedProductId" in js
        assert "parseFloat" not in js
        assert "weightInput.value.trim()" in js

    def test_product_unavailable_handling_and_utf8(self, client):
        resp = client.get("/static/js/reception.js")
        js = resp.data.decode()
        assert "product_unavailable" in js
        assert "loadProducts" in js
        assert "Código" in js
        assert "&aacute;" not in js
        assert "&oacute;" not in js
