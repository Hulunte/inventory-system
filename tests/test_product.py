import os
import time

import pytest
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.models.product import Product
from app.extensions import db
from app.services.product_service import (
    DuplicateProductError,
    _validate_rate,
    _validate_name,
    _format_rate,
    _is_duplicate_product_name_error,
    create_product,
    update_product,
    search_products,
    activate_product,
    deactivate_product,
    serialize_product,
)


@pytest.fixture(autouse=True)
def _clean_products(db_session):
    db_session.execute(Product.__table__.delete())
    db_session.flush()
    yield


# ---------------------------------------------------------------------------
# Model (PostgreSQL protections — not redundant with service tests)
# ---------------------------------------------------------------------------

class TestProductModel:
    def test_create_and_defaults(self, db_session):
        product = Product(name="Chile", rate_per_kg=Decimal("4.75"))
        db_session.add(product)
        db_session.commit()
        assert product.id is not None
        assert product.name == "Chile"
        assert product.rate_per_kg == Decimal("4.75")
        assert product.active is True
        assert product.created_at is not None
        assert product.updated_at is not None

    def test_timestamps_utc(self, db_session):
        product = Product(name="Cebolla", rate_per_kg=Decimal("2.50"))
        db_session.add(product)
        db_session.commit()
        assert product.created_at.tzinfo is not None
        assert product.updated_at.tzinfo is not None

    def test_check_constraint_negative_rate(self, db_session):
        product = Product(name="Bad", rate_per_kg=Decimal("-1.00"))
        db_session.add(product)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_duplicate_case_insensitive(self, db_session):
        p1 = Product(name="Chile", rate_per_kg=Decimal("4.75"))
        db_session.add(p1)
        db_session.commit()

        p2 = Product(name="chile", rate_per_kg=Decimal("5.00"))
        db_session.add(p2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


# ---------------------------------------------------------------------------
# Validation pure functions
# ---------------------------------------------------------------------------

class TestValidateRate:
    @pytest.mark.parametrize("value,expected", [
        ("4.75", Decimal("4.75")),
        ("0", Decimal("0")),
        ("0.00", Decimal("0.00")),
        ("100.10", Decimal("100.10")),
        ("999999.99", Decimal("999999.99")),
        (Decimal("4.75"), Decimal("4.75")),
        (4, Decimal("4")),
    ])
    def test_valid_rates(self, value, expected):
        assert _validate_rate(value) == expected

    @pytest.mark.parametrize("value", [
        4.75,
        True,
        None,
        "",
        "   ",
        "NaN",
        "Infinity",
        "-1",
        "1e2",
        "4.759",
        "1000000.00",
    ])
    def test_invalid_rates(self, value):
        with pytest.raises(ValueError):
            _validate_rate(value)


class TestValidateName:
    @pytest.mark.parametrize("bad_name", [123, True, [1, 2], {"a": 1}])
    def test_invalid_type_rejected(self, bad_name):
        with pytest.raises(ValueError, match="must be a string"):
            _validate_name(bad_name)

    @pytest.mark.parametrize("bad_name", ["", "   "])
    def test_empty_or_whitespace_rejected(self, bad_name):
        with pytest.raises(ValueError, match="required"):
            _validate_name(bad_name)

    def test_101_chars_rejected(self):
        with pytest.raises(ValueError, match="too long"):
            _validate_name("A" * 101)

    def test_100_chars_accepted(self):
        assert _validate_name("A" * 100) == "A" * 100

    def test_strips_whitespace(self):
        assert _validate_name("  Chile  ") == "Chile"


class TestFormatRate:
    @pytest.mark.parametrize("value,expected", [
        (Decimal("4.75"), "4.75"),
        (Decimal("0"), "0.00"),
        (Decimal("100.1"), "100.10"),
    ])
    def test_format_two_decimals(self, value, expected):
        assert _format_rate(value) == expected


# ---------------------------------------------------------------------------
# Service: create_product
# ---------------------------------------------------------------------------

class TestCreateProduct:
    def test_happy_path(self, db_session):
        product = create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        assert product.id is not None
        assert product.name == "Chile"
        assert product.rate_per_kg == Decimal("4.75")
        assert product.active is True

    def test_invalid_rate_does_not_create(self, db_session):
        with pytest.raises(ValueError):
            create_product(name="Chile", rate_per_kg=4.75)
        assert Product.query.count() == 0

    def test_invalid_name_does_not_create(self, db_session):
        with pytest.raises(ValueError, match="must be a string"):
            create_product(name=123, rate_per_kg=Decimal("4.75"))
        assert Product.query.count() == 0

    def test_duplicate_case_insensitive(self, db_session):
        create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        with pytest.raises(DuplicateProductError):
            create_product(name="chile", rate_per_kg=Decimal("5.00"))

    def test_integrity_error_rollback(self, db_session):
        create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        with pytest.raises(DuplicateProductError):
            create_product(name="CHILE", rate_per_kg=Decimal("6.00"))
        product = create_product(name="Cebolla", rate_per_kg=Decimal("3.00"))
        assert product.id is not None


# ---------------------------------------------------------------------------
# Service: update_product
# ---------------------------------------------------------------------------

class TestUpdateProduct:
    def test_happy_path(self, db_session):
        product = create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        updated = update_product(product.id, name="Chile rojo", rate_per_kg=Decimal("6.00"))
        assert updated.name == "Chile rojo"
        assert updated.rate_per_kg == Decimal("6.00")

    def test_validates_provided_fields(self, db_session):
        product = create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        with pytest.raises(ValueError, match="must be a string"):
            update_product(product.id, name=123)
        with pytest.raises(ValueError):
            update_product(product.id, rate_per_kg=4.75)

    def test_invalid_rate_does_not_modify(self, db_session):
        product = create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        original_rate = product.rate_per_kg
        with pytest.raises(ValueError):
            update_product(product.id, rate_per_kg=4.75)
        refreshed = db.session.get(Product, product.id)
        assert refreshed.rate_per_kg == original_rate

    def test_not_found(self, db_session):
        result = update_product(99999, name="Test")
        assert result is None

    def test_duplicate_name(self, db_session):
        create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        cebolla = create_product(name="Cebolla", rate_per_kg=Decimal("3.00"))
        with pytest.raises(DuplicateProductError):
            update_product(cebolla.id, name="Chile")

    def test_omitted_field_preserves_value(self, db_session):
        product = create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        updated = update_product(product.id, name="Chile habanero")
        assert updated.name == "Chile habanero"
        assert updated.rate_per_kg == Decimal("4.75")

    def test_updates_timestamp(self, db_session):
        product = create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        original_updated = product.updated_at
        time.sleep(0.01)
        updated = update_product(product.id, rate_per_kg=Decimal("5.00"))
        assert updated.updated_at >= original_updated


# ---------------------------------------------------------------------------
# Service: search_products
# ---------------------------------------------------------------------------

class TestSearchProducts:
    def test_search_by_name(self, db_session):
        create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        create_product(name="Cebolla", rate_per_kg=Decimal("3.00"))
        results = search_products("Chile")
        assert len(results) == 1
        assert results[0].name == "Chile"

    def test_search_case_insensitive(self, db_session):
        create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        results = search_products("chile")
        assert len(results) == 1

    def test_search_no_results(self, db_session):
        create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        results = search_products("ZZZZ")
        assert len(results) == 0

    def test_order_by_name(self, db_session):
        create_product(name="Tomate", rate_per_kg=Decimal("3.00"))
        create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        create_product(name="Aceite", rate_per_kg=Decimal("2.00"))
        results = search_products()
        names = [p.name for p in results]
        assert names == ["Aceite", "Chile", "Tomate"]


# ---------------------------------------------------------------------------
# Service: activate / deactivate
# ---------------------------------------------------------------------------

class TestActivateDeactivateProduct:
    def test_activate_and_deactivate(self, db_session):
        product = create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        result = deactivate_product(product.id)
        assert result.active is False
        result = activate_product(product.id)
        assert result.active is True

    def test_activate_deactivate_not_found(self, db_session):
        assert deactivate_product(99999) is None
        assert activate_product(99999) is None


# ---------------------------------------------------------------------------
# Service: serialize_product
# ---------------------------------------------------------------------------

class TestSerializeProduct:
    @pytest.mark.parametrize("rate,expected", [
        (Decimal("4.75"), "4.75"),
        (Decimal("0"), "0.00"),
        (Decimal("100.1"), "100.10"),
    ])
    def test_rate_formatted_two_decimals(self, db_session, rate, expected):
        product = create_product(name="Chile", rate_per_kg=rate)
        result = serialize_product(product)
        assert result["rate_per_kg"] == expected

    def test_all_fields_present(self, db_session):
        product = create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        result = serialize_product(product)
        assert set(result.keys()) == {
            "id", "name", "rate_per_kg", "active", "created_at", "updated_at"
        }


# ---------------------------------------------------------------------------
# IntegrityError classification
# ---------------------------------------------------------------------------

class TestIntegrityErrorClassification:
    def test_duplicate_raises_duplicate_error(self, db_session):
        create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        with pytest.raises(DuplicateProductError):
            create_product(name="chile", rate_per_kg=Decimal("5.00"))
        p = create_product(name="Cebolla", rate_per_kg=Decimal("3.00"))
        assert p.id is not None

    def test_non_duplicate_raises_integrity_error(self, db_session):
        product = Product(name="Bad", rate_per_kg=Decimal("-1.00"))
        db_session.add(product)
        with pytest.raises(IntegrityError) as exc_info:
            db_session.commit()
        assert _is_duplicate_product_name_error(exc_info.value) is False

    def test_session_usable_after_duplicate(self, db_session):
        create_product(name="Chile", rate_per_kg=Decimal("4.75"))
        with pytest.raises(DuplicateProductError):
            create_product(name="chile", rate_per_kg=Decimal("5.00"))
        p1 = create_product(name="Cebolla", rate_per_kg=Decimal("3.00"))
        p2 = create_product(name="Tomate", rate_per_kg=Decimal("2.50"))
        assert p1.id is not None
        assert p2.id is not None


# ---------------------------------------------------------------------------
# Endpoint helpers
# ---------------------------------------------------------------------------

def _get_csrf(admin_client):
    return admin_client.get("/api/admin/session").get_json()["csrf_token"]


def _create_product(admin_client, name="Chile", rate="4.75"):
    csrf = _get_csrf(admin_client)
    resp = admin_client.post(
        "/api/admin/products",
        json={"name": name, "rate_per_kg": rate},
        headers={"X-CSRF-Token": csrf},
    )
    return resp, csrf


# ---------------------------------------------------------------------------
# Endpoints: GET / PATCH / activate / deactivate
# ---------------------------------------------------------------------------

class TestProductEndpoints:
    def test_get_products_empty(self, admin_client, db_session):
        response = admin_client.get("/api/admin/products")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_post_product_valid(self, admin_client, db_session):
        resp, _ = _create_product(admin_client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Chile"
        assert data["rate_per_kg"] == "4.75"
        assert data["active"] is True

    def test_post_product_rate_zero(self, admin_client, db_session):
        resp, _ = _create_product(admin_client, name="Proximamente", rate="0.00")
        assert resp.status_code == 201
        assert resp.get_json()["rate_per_kg"] == "0.00"

    def test_post_product_duplicate(self, admin_client, db_session):
        csrf = _get_csrf(admin_client)
        _create_product(admin_client)
        resp = admin_client.post(
            "/api/admin/products",
            json={"name": "chile", "rate_per_kg": "5.00"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 409

    def test_patch_product_valid(self, admin_client, db_session):
        csrf = _get_csrf(admin_client)
        post_resp = _create_product(admin_client)
        product_id = post_resp[0].get_json()["id"]
        resp = admin_client.patch(
            f"/api/admin/products/{product_id}",
            json={"name": "Chile rojo", "rate_per_kg": "5.50"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == "Chile rojo"
        assert data["rate_per_kg"] == "5.50"

    def test_patch_product_not_found(self, admin_client, db_session):
        csrf = _get_csrf(admin_client)
        resp = admin_client.patch(
            "/api/admin/products/99999",
            json={"name": "Test"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 404

    def test_patch_product_duplicate_name(self, admin_client, db_session):
        csrf = _get_csrf(admin_client)
        _create_product(admin_client, name="Chile")
        post2 = _create_product(admin_client, name="Cebolla")
        product_id = post2[0].get_json()["id"]
        resp = admin_client.patch(
            f"/api/admin/products/{product_id}",
            json={"name": "Chile"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 409

    def test_activate_and_deactivate(self, admin_client, db_session):
        csrf = _get_csrf(admin_client)
        post_resp = _create_product(admin_client)
        product_id = post_resp[0].get_json()["id"]

        resp = admin_client.patch(
            f"/api/admin/products/{product_id}/deactivate",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200
        assert resp.get_json()["active"] is False

        resp = admin_client.patch(
            f"/api/admin/products/{product_id}/activate",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200
        assert resp.get_json()["active"] is True

    def test_activate_deactivate_not_found(self, admin_client, db_session):
        csrf = _get_csrf(admin_client)
        for path in ["/api/admin/products/99999/activate",
                     "/api/admin/products/99999/deactivate"]:
            resp = admin_client.patch(path, headers={"X-CSRF-Token": csrf})
            assert resp.status_code == 404

    def test_get_products_includes_inactive(self, admin_client, db_session):
        csrf = _get_csrf(admin_client)
        _create_product(admin_client, name="Chile")
        _create_product(admin_client, name="Cebolla")

        all_products = admin_client.get("/api/admin/products").get_json()
        cebolla_id = next(p["id"] for p in all_products if p["name"] == "Cebolla")

        admin_client.patch(
            f"/api/admin/products/{cebolla_id}/deactivate",
            headers={"X-CSRF-Token": csrf},
        )

        data = admin_client.get("/api/admin/products").get_json()
        assert len(data) == 2
        assert sum(1 for p in data if p["active"]) == 1
        assert sum(1 for p in data if not p["active"]) == 1

    def test_get_products_search(self, admin_client, db_session):
        _create_product(admin_client, name="Chile")
        _create_product(admin_client, name="Cebolla")

        data = admin_client.get("/api/admin/products?q=chile").get_json()
        assert len(data) == 1
        assert data[0]["name"] == "Chile"


# ---------------------------------------------------------------------------
# Endpoint JSON body validation: POST
# ---------------------------------------------------------------------------

class TestPostJsonBodyValidation:
    @pytest.mark.parametrize("body", [[], "texto", 123, True, None])
    def test_non_object_json_returns_400(self, admin_client, db_session, body):
        csrf = _get_csrf(admin_client)
        raw = "null" if body is None else (
            "true" if body is True else str(body)
        )
        resp = admin_client.post(
            "/api/admin/products",
            content_type="application/json",
            data=raw,
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("body", ["{invalid", "{}"])
    def test_malformed_or_empty_json_returns_400(self, admin_client, db_session, body):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/admin/products",
            content_type="application/json",
            data=body,
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("payload", [
        {"rate_per_kg": "4.75"},
        {"name": "Chile"},
    ])
    def test_missing_required_field_returns_400(self, admin_client, db_session, payload):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/admin/products",
            json=payload,
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("field", ["name", "rate_per_kg"])
    def test_null_field_returns_400(self, admin_client, db_session, field):
        csrf = _get_csrf(admin_client)
        payload = {"name": "Chile", "rate_per_kg": "4.75", field: None}
        resp = admin_client.post(
            "/api/admin/products",
            json=payload,
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_unknown_fields_returns_400(self, admin_client, db_session):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/admin/products",
            json={"name": "Chile", "rate_per_kg": "4.75", "extra": "field"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_name", [123, True, [1, 2], {"a": 1}])
    def test_invalid_name_type_returns_400(self, admin_client, db_session, bad_name):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/admin/products",
            json={"name": bad_name, "rate_per_kg": "4.75"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_float_rate_returns_400(self, admin_client, db_session):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/admin/products",
            json={"name": "Chile", "rate_per_kg": 4.75},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_duplicate_returns_409_and_no_product_created(self, admin_client, db_session):
        _create_product(admin_client, name="Chile")
        _create_product(admin_client, name="Cebolla")
        resp, _ = _create_product(admin_client, name="chile", rate="5.00")
        assert resp.status_code == 409
        assert len(admin_client.get("/api/admin/products").get_json()) == 2


# ---------------------------------------------------------------------------
# Endpoint JSON body validation: PATCH
# ---------------------------------------------------------------------------

class TestPatchJsonBodyValidation:
    @pytest.mark.parametrize("body", [[], "texto", 123, True, None])
    def test_non_object_json_returns_400(self, admin_client, db_session, body):
        csrf = _get_csrf(admin_client)
        post_resp, _ = _create_product(admin_client)
        product_id = post_resp.get_json()["id"]
        raw = "null" if body is None else (
            "true" if body is True else str(body)
        )
        resp = admin_client.patch(
            f"/api/admin/products/{product_id}",
            content_type="application/json",
            data=raw,
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("body", ["{invalid", "{}"])
    def test_malformed_or_empty_json_returns_400(self, admin_client, db_session, body):
        csrf = _get_csrf(admin_client)
        post_resp, _ = _create_product(admin_client)
        product_id = post_resp.get_json()["id"]
        resp = admin_client.patch(
            f"/api/admin/products/{product_id}",
            content_type="application/json",
            data=body,
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("field", ["name", "rate_per_kg"])
    def test_null_field_returns_400(self, admin_client, db_session, field):
        csrf = _get_csrf(admin_client)
        post_resp, _ = _create_product(admin_client)
        product_id = post_resp.get_json()["id"]
        resp = admin_client.patch(
            f"/api/admin/products/{product_id}",
            json={field: None},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_unknown_fields_returns_400(self, admin_client, db_session):
        csrf = _get_csrf(admin_client)
        post_resp, _ = _create_product(admin_client)
        product_id = post_resp.get_json()["id"]
        resp = admin_client.patch(
            f"/api/admin/products/{product_id}",
            json={"name": "Chile", "unknown_field": "value"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_rate_only_preserves_name(self, admin_client, db_session):
        csrf = _get_csrf(admin_client)
        post_resp, _ = _create_product(admin_client)
        product_id = post_resp.get_json()["id"]
        resp = admin_client.patch(
            f"/api/admin/products/{product_id}",
            json={"rate_per_kg": "5.50"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == "Chile"
        assert data["rate_per_kg"] == "5.50"

    def test_name_only_preserves_rate(self, admin_client, db_session):
        csrf = _get_csrf(admin_client)
        post_resp, _ = _create_product(admin_client)
        product_id = post_resp.get_json()["id"]
        resp = admin_client.patch(
            f"/api/admin/products/{product_id}",
            json={"name": "Chile habanero"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == "Chile habanero"
        assert data["rate_per_kg"] == "4.75"


# ---------------------------------------------------------------------------
# Auth / CSRF parametrized
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,endpoint", [
    ("get", "/api/admin/products"),
    ("post", "/api/admin/products"),
    ("patch", "/api/admin/products/1"),
])
def test_product_requires_auth(client, method, endpoint):
    resp = getattr(client, method)(endpoint, json={})
    assert resp.status_code == 401


@pytest.mark.parametrize("method,endpoint", [
    ("post", "/api/admin/products"),
    ("patch", "/api/admin/products/1"),
])
def test_product_requires_csrf(admin_client, method, endpoint):
    resp = getattr(admin_client, method)(endpoint, json={})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# HTML admin page
# ---------------------------------------------------------------------------

class TestProductAdminPage:
    def test_section_form_and_modal_present(self, admin_client):
        html = admin_client.get("/admin").data.decode()
        assert 'id="products-section"' in html
        assert 'id="product-form"' in html
        assert 'id="edit-product-modal"' in html

    def test_create_form_attributes(self, admin_client):
        html = admin_client.get("/admin").data.decode()
        assert 'id="product-name"' in html
        assert 'maxlength="100"' in html
        assert 'id="product-rate"' in html
        assert 'min="0"' in html
        assert 'max="999999.99"' in html
        assert 'step="0.01"' in html
        assert 'inputmode="decimal"' in html

    def test_edit_form_attributes(self, admin_client):
        html = admin_client.get("/admin").data.decode()
        assert 'id="edit-product-name"' in html
        assert 'maxlength="100"' in html
        assert 'id="edit-product-rate"' in html
        assert 'min="0"' in html
        assert 'max="999999.99"' in html
        assert 'step="0.01"' in html
        assert 'inputmode="decimal"' in html

    def test_label_and_no_inline_style(self, admin_client):
        html = admin_client.get("/admin").data.decode()
        assert "Precio por kg (MXN)" in html
        assert "Tarifa por kg (MXN)" not in html
        assert 'style="margin-top: 1rem;"' not in html


# ---------------------------------------------------------------------------
# Residual data isolation verification
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _insert_residual_product(app):
    """Insert a committed residual product BEFORE any test in this module.

    The raw connection commits outside the test transaction, simulating
    leftover data from a previous run.  _clean_products must remove it.
    """
    from dotenv import load_dotenv
    load_dotenv()
    raw_engine = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        with raw_engine.begin() as conn:
            conn.execute(text("DELETE FROM products WHERE name = :n"), {"n": "ResidualChile"})
            result = conn.execute(
                text("SELECT count(*) FROM products WHERE name = :n"), {"n": "ResidualChile"}
            )
            assert result.scalar() == 0, "DELETE of pre-existing ResidualChile failed"

        with raw_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO products (name, rate_per_kg, active, created_at, updated_at) "
                    "VALUES (:n, :r, true, NOW(), NOW())"
                ),
                {"n": "ResidualChile", "r": "9.99"},
            )

        yield
    finally:
        try:
            with raw_engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM products WHERE name = :n"), {"n": "ResidualChile"}
                )
        finally:
            raw_engine.dispose()


class TestResidualDataIsolation:
    def test_clean_products_removes_residual_data(self, db_session):
        """Verify _clean_products deleted the committed residual product.

        The residual was inserted via a raw connection (committed outside
        the test transaction).  _clean_products runs DELETE + flush before
        this test.  The products table must be empty.
        """
        from sqlalchemy import select
        result = db_session.execute(select(Product))
        products = result.fetchall()
        assert len(products) == 0, (
            f"_clean_products did not remove residual data: {products}"
        )
