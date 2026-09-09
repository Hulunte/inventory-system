"""Phase 3: explicit, auditable sack-based harvest registration."""
from datetime import date
from decimal import Decimal
from sqlalchemy import event

import pytest

from app.extensions import db
from app.models.harvest_entry import HarvestEntry
from app.models.product import Product
from app.services.ticket_service import get_daily_tickets, serialize_daily_response
from tests.conftest import make_worker_with_assignment


def _csrf(client):
    return client.get("/api/admin/session").get_json()["csrf_token"]


def _setup(db_session, *, average="18.500"):
    worker, assignment = make_worker_with_assignment(
        db_session, slot_number=148, person_name="Persona Arpillas"
    )
    product = Product(
        name="Limón Arpillas",
        rate_per_kg=Decimal("4.25"),
        average_sack_weight_kg=Decimal(average) if average is not None else None,
        active=True,
    )
    db_session.add(product)
    db_session.commit()
    return worker, assignment, product


def _post(admin_client, worker, product, count=3, csrf=None):
    return admin_client.post(
        "/api/harvest/sack-entries",
        json={"barcode": worker.barcode, "product_id": product.id, "sack_count": count},
        headers={"X-CSRF-Token": csrf if csrf is not None else _csrf(admin_client)},
    )


def test_sack_mode_ui_switch_preview_and_return(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="open-sacks-mode"' in html
    assert 'id="sacks-mode"' in html
    assert 'id="close-sacks-mode"' in html
    assert 'id="recent-movements"' in html
    js = client.get("/static/js/sacks.js").get_data(as_text=True)
    assert "receptionMain.hidden = true" in js
    assert "receptionMain.hidden = false" in js
    assert "loadRecentMovements()" in js
    assert 'id="sacks-product-buttons"' in html
    assert '<select id="sacks-product"' not in html


def test_sack_product_buttons_support_selection_and_change(client):
    js = client.get("/static/js/sacks.js").get_data(as_text=True)
    assert 'class="product-button sacks-product-button"' in js
    assert 'role="radio"' in js
    assert 'setAttribute("aria-checked", String(item === button))' in js
    assert "selectedSacksProductId = Number(button.dataset.productId)" in js


def test_active_product_endpoint_drives_sack_buttons_and_excludes_inactive(client, db_session):
    db_session.add_all([
        Product(name="Activo arpillas", rate_per_kg=Decimal("2.00"), average_sack_weight_kg=Decimal("10.000"), active=True),
        Product(name="Inactivo arpillas", rate_per_kg=Decimal("2.00"), average_sack_weight_kg=Decimal("10.000"), active=False),
    ])
    db_session.commit()
    response = client.get("/api/products/active")
    assert response.status_code == 200
    names = {product["name"] for product in response.get_json()}
    assert "Activo arpillas" in names
    assert "Inactivo arpillas" not in names


def test_register_sacks_calculates_weight_amount_and_snapshots(admin_client, db_session):
    worker, assignment, product = _setup(db_session)
    response = _post(admin_client, worker, product, count=3)
    assert response.status_code == 201
    data = response.get_json()
    assert data["weight_kg"] == "55.500"
    assert data["amount_mxn"] == "235.88"
    assert data["estimated_weight"] is True
    entry = db.session.get(HarvestEntry, data["id"])
    assert entry.worker_assignment_id == assignment.id
    assert entry.registration_type == "sacks"
    assert entry.sack_count == 3
    assert entry.average_sack_weight_kg_snapshot == Decimal("18.500")
    assert entry.product_name_snapshot == product.name
    assert entry.worker_barcode_snapshot == worker.barcode


@pytest.mark.parametrize("count", [None, 0, -1, 1.5, "2", True])
def test_invalid_sack_count_is_rejected(admin_client, db_session, count):
    worker, _, product = _setup(db_session)
    response = _post(admin_client, worker, product, count=count)
    assert response.status_code == 400


def test_sack_registration_requires_admin_and_csrf(client, admin_client, db_session):
    worker, _, product = _setup(db_session)
    payload = {"barcode": worker.barcode, "product_id": product.id, "sack_count": 1}
    assert client.post("/api/harvest/sack-entries", json=payload).status_code == 401
    assert admin_client.post("/api/harvest/sack-entries", json=payload).status_code == 403
    assert _post(admin_client, worker, product, csrf="incorrecto").status_code == 403


def test_missing_average_does_not_invent_weight(admin_client, db_session):
    worker, _, product = _setup(db_session, average=None)
    response = _post(admin_client, worker, product)
    assert response.status_code == 409
    assert response.get_json()["error"] == "Promedio no disponible"
    assert HarvestEntry.query.count() == 0


def test_product_average_can_be_configured_and_validated(admin_client):
    csrf = _csrf(admin_client)
    created = admin_client.post(
        "/api/admin/products",
        json={"name": "Producto promedio", "rate_per_kg": "3.00", "average_sack_weight_kg": "21.250"},
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201
    assert created.get_json()["average_sack_weight_kg"] == "21.250"
    invalid = admin_client.patch(
        f"/api/admin/products/{created.get_json()['id']}",
        json={"average_sack_weight_kg": "0"},
        headers={"X-CSRF-Token": csrf},
    )
    assert invalid.status_code == 400


def test_invalid_worker_and_product(admin_client, db_session):
    worker, _, product = _setup(db_session)
    csrf = _csrf(admin_client)
    missing_worker = admin_client.post(
        "/api/harvest/sack-entries",
        json={"barcode": "INVALIDO", "product_id": product.id, "sack_count": 1},
        headers={"X-CSRF-Token": csrf},
    )
    assert missing_worker.status_code == 404
    missing_product = admin_client.post(
        "/api/harvest/sack-entries",
        json={"barcode": worker.barcode, "product_id": 999999, "sack_count": 1},
        headers={"X-CSRF-Token": csrf},
    )
    assert missing_product.status_code == 409


def test_worker_without_assignment_is_rejected(admin_client, db_session):
    from tests.conftest import make_worker

    worker = make_worker(db_session, slot_number=146)
    product = Product(
        name="Producto sin asignación", rate_per_kg=Decimal("2.00"),
        average_sack_weight_kg=Decimal("10.000"), active=True,
    )
    db_session.add(product)
    db_session.commit()
    response = _post(admin_client, worker, product, count=1)
    assert response.status_code == 409
    assert response.get_json()["code"] == "worker_unassigned"


def test_sack_statistics_are_auditable(admin_client, db_session):
    worker, _, product = _setup(db_session)
    _post(admin_client, worker, product, count=2)
    _post(admin_client, worker, product, count=3)
    response = admin_client.get(
        f"/api/harvest/sack-statistics/{product.id}",
        headers={"X-CSRF-Token": _csrf(admin_client)},
    )
    data = response.get_json()
    assert response.status_code == 200
    assert data["total_movements"] == 2
    assert data["total_sacks"] == 5
    assert data["total_kg"] == "92.500"
    assert data["average_kg_per_movement"] == "46.250"
    assert data["average_kg_per_sack"] == "18.500"
    assert data["period"]


def test_recent_history_report_and_ticket_separate_estimated_weight(admin_client, db_session, app):
    worker, assignment, product = _setup(db_session)
    _post(admin_client, worker, product, count=2)
    recent = admin_client.get("/api/harvest/recent").get_json()["movements"][0]
    assert recent["registration_type_label"] == "Arpillas"
    assert recent["estimated_weight"] is True
    assert recent["sack_count"] == 2

    operational_date = recent_date = HarvestEntry.query.first().created_at.astimezone(
        app.config["HARVEST_TIMEZONE"]
    ).date()
    history = admin_client.get(
        f"/api/history/assignments/{assignment.id}/entries?date={recent_date.isoformat()}"
    ).get_json()["entries"][0]
    assert history["registration_type_label"] == "Arpillas"
    report = admin_client.get(
        f"/api/reports/harvest?start_date={recent_date.isoformat()}&end_date={recent_date.isoformat()}"
    ).get_json()["workers"][0]
    assert report["sack_entries_count"] == 1
    assert report["scale_entries_count"] == 0
    ticket = serialize_daily_response(get_daily_tickets(operational_date))["tickets"][0]
    assert ticket["product_lines"][0]["registration_type_label"] == "Arpillas"
    assert ticket["product_lines"][0]["estimated_weight"] is True


def test_real_product_and_recent_endpoints_serialize_without_500(client, db_session):
    _, _, product = _setup(db_session)
    products = client.get("/api/products/active")
    recent = client.get("/api/harvest/recent?limit=10")
    assert products.status_code == 200
    assert recent.status_code == 200
    assert products.is_json and recent.is_json
    assert products.get_json()[0]["average_sack_weight_kg"] == "18.500"
    assert recent.get_json() == {"movements": []}


def test_recent_serialization_supports_anonymous_historical_worker(client, db_session):
    worker, assignment, product = _setup(db_session)
    entry = HarvestEntry(
        worker_id=worker.id, worker_assignment_id=assignment.id, product_id=product.id,
        weight_kg=Decimal("10.000"), amount_mxn=Decimal("42.50"),
        product_name_snapshot=product.name, rate_per_kg_snapshot=product.rate_per_kg,
        worker_name_snapshot="Sin nombre", worker_barcode_snapshot=worker.barcode,
        worker_slot_number_snapshot=worker.slot_number,
    )
    db_session.add(entry)
    db_session.commit()
    response = client.get("/api/harvest/recent")
    assert response.status_code == 200
    assert response.get_json()["movements"][0]["worker"]["name"] == "Sin nombre"


def test_scale_entries_remain_measured(db_session):
    worker, assignment, product = _setup(db_session)
    entry = HarvestEntry(
        worker_id=worker.id,
        worker_assignment_id=assignment.id,
        product_id=product.id,
        weight_kg=Decimal("10.000"),
        amount_mxn=Decimal("42.50"),
        product_name_snapshot=product.name,
        rate_per_kg_snapshot=product.rate_per_kg,
        worker_name_snapshot=assignment.person_name,
        worker_barcode_snapshot=worker.barcode,
        worker_slot_number_snapshot=worker.slot_number,
    )
    db_session.add(entry)
    db_session.commit()
    assert entry.registration_type == "scale"
    assert entry.sack_count is None
    assert entry.average_sack_weight_kg_snapshot is None


def test_sack_entry_can_be_voided_without_losing_snapshots(admin_client, db_session):
    worker, _, product = _setup(db_session)
    entry_id = _post(admin_client, worker, product, count=4).get_json()["id"]
    response = admin_client.patch(
        f"/api/admin/harvest-entries/{entry_id}/void",
        json={"reason": "Anulación rápida"},
        headers={"X-CSRF-Token": _csrf(admin_client)},
    )
    assert response.status_code == 200
    entry = db.session.get(HarvestEntry, entry_id)
    assert entry.voided is True
    assert entry.sack_count == 4
    assert entry.average_sack_weight_kg_snapshot == Decimal("18.500")
    assert entry.product_name_snapshot == product.name


def test_migration_is_additive_and_reversible():
    migration = (
        __import__("pathlib").Path(__file__).parents[1]
        / "migrations" / "versions" / "e2f3a4b5c6d7_add_sack_registration_fields.py"
    ).read_text(encoding="utf-8")
    assert "def upgrade()" in migration
    assert "def downgrade()" in migration
    assert "server_default=\"scale\"" in migration
    assert "UPDATE harvest_entries" not in migration


def test_phase3_endpoints_respond_after_current_schema(client, db_session):
    product = Product(
        name="Producto esquema actual",
        rate_per_kg=Decimal("2.50"),
        average_sack_weight_kg=None,
        active=True,
    )
    db_session.add(product)
    db_session.commit()

    products = client.get("/api/products/active")
    recent = client.get("/api/harvest/recent")

    assert products.status_code == 200
    assert any(item["id"] == product.id for item in products.get_json())
    assert recent.status_code == 200
    assert "movements" in recent.get_json()


def test_sacks_script_prevents_double_submit_and_never_uses_scale(client):
    js = client.get("/static/js/sacks.js").get_data(as_text=True)
    assert "if (sacksBusy) return" in js
    assert "scale-connect" not in js
    assert "scale-reading" not in js
    assert 'fetch("/api/products/active")' not in js
    assert "window.receptionProductsReady" in js
    assert "sack-statistics/" not in js


def test_sack_product_buttons_have_responsive_non_native_states(client):
    html = client.get("/").get_data(as_text=True)
    css = client.get("/static/css/reception.css").get_data(as_text=True)
    assert 'id="sacks-product-buttons"' in html
    assert 'role="radiogroup"' in html
    assert "appearance: none" in css
    assert "grid-template-columns: repeat(auto-fit, minmax(180px, 1fr))" in css
    assert '.sacks-product-button[aria-checked="true"]' in css
    assert ".sacks-product-button:hover" in css
    assert ".sacks-product-button:focus-visible" in css
    assert ".sacks-product-button:active" in css


def test_reception_queries_are_constant_without_n_plus_one(admin_client, client, db_session, app):
    worker, _, first_product = _setup(db_session)
    _post(admin_client, worker, first_product, count=2)
    for index in range(20):
        db_session.add(Product(
            name=f"Producto consulta {index:02d}",
            rate_per_kg=Decimal("2.00"),
            average_sack_weight_kg=Decimal("15.000"),
            active=True,
        ))
    db_session.commit()

    statements = []
    engine = app.extensions["sqlalchemy"].engine

    def count_selects(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        products = client.get("/api/products/active")
        product_selects = len(statements)
        statements.clear()
        recent = client.get("/api/harvest/recent?limit=10")
        recent_selects = len(statements)
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    assert products.status_code == 200
    assert len(products.get_json()) == 21
    assert product_selects == 1
    assert recent.status_code == 200
    assert recent_selects == 1
