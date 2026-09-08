from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models.harvest_entry import HarvestEntry
from app.models.product import Product
from tests.conftest import make_worker_with_assignment


@pytest.fixture
def voided_entry(db_session):
    worker, assignment = make_worker_with_assignment(
        db_session, name="Nombre snapshot anulado", slot_number=149
    )
    product = Product(name="Producto snapshot anulado", rate_per_kg=Decimal("12.50"))
    db_session.add(product)
    db_session.flush()
    entry = HarvestEntry(
        worker_id=worker.id,
        worker_assignment_id=assignment.id,
        worker_slot_number_snapshot=149,
        worker_barcode_snapshot="TRB-SNAPSHOT-149",
        worker_name_snapshot="Nombre snapshot anulado",
        product_id=product.id,
        product_name_snapshot="Producto histórico especial",
        rate_per_kg_snapshot=Decimal("12.50"),
        weight_kg=Decimal("4.000"),
        amount_mxn=Decimal("50.00"),
        created_at=datetime(2026, 9, 5, 14, 30, tzinfo=timezone.utc),
        voided=True,
        void_reason="Captura duplicada",
        voided_at=datetime(2026, 9, 5, 15, 0, tzinfo=timezone.utc),
    )
    db_session.add(entry)
    db_session.commit()
    return entry


def test_voids_page_and_api_require_admin(client, db_session):
    page = client.get("/anulaciones")
    assert page.status_code == 302
    assert "/admin/login" in page.headers["Location"]
    assert client.get("/api/voids").status_code == 401


def test_voids_page_is_read_only_has_csrf_and_navigation(admin_client, db_session):
    page = admin_client.get("/anulaciones")
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "Anulaciones" in html
    assert 'meta name="csrf-token"' in html
    assert 'href="/anulaciones"' in html
    assert "Trabajador, código, cupo o producto" in html
    assert 'id="active-entries-content"' in html
    assert 'id="void-modal"' in html
    assert 'id="void-reason-input"' in html


def test_voids_api_uses_historical_snapshots(admin_client, voided_entry):
    response = admin_client.get("/api/voids")
    assert response.status_code == 200
    item = next(row for row in response.get_json()["entries"] if row["id"] == voided_entry.id)
    assert item["worker_name"] == "Nombre snapshot anulado"
    assert item["worker_barcode"] == "TRB-SNAPSHOT-149"
    assert item["slot_number"] == 149
    assert item["product_name"] == "Producto histórico especial"
    assert item["weight_kg"] == "4.000"
    assert item["amount_mxn"] == "50.00"
    assert item["void_reason"] == "Captura duplicada"
    assert item["date"] and item["time"] and item["voided_at"]


@pytest.mark.parametrize(
    "query", ["Nombre snapshot", "TRB-SNAPSHOT", "149", "histórico especial"]
)
def test_voids_searches_snapshots(admin_client, voided_entry, query):
    response = admin_client.get("/api/voids", query_string={"q": query})
    assert response.status_code == 200
    assert voided_entry.id in [row["id"] for row in response.get_json()["entries"]]


def test_main_navigation_links_to_voids(admin_client, db_session):
    for path in ("/admin", "/admin/products", "/history", "/reports", "/tickets"):
        response = admin_client.get(path)
        assert response.status_code == 200
        assert 'href="/anulaciones"' in response.get_data(as_text=True)


def test_admin_no_longer_contains_void_interaction(admin_client, db_session):
    html = admin_client.get("/admin").get_data(as_text=True)
    js = admin_client.get("/static/js/admin.js").get_data(as_text=True)
    assert 'id="entries-section"' not in html
    assert 'id="void-modal"' not in html
    assert "loadEntries" not in js
    assert "currentVoidEntryId" not in js
    assert "/void`" not in js


def test_voids_javascript_has_active_product_confirmation_reason_and_csrf(client):
    source = client.get("/static/js/voids.js").get_data(as_text=True)
    assert "/api/admin/harvest-entries?date=" in source
    assert "entry.product_name" in source
    assert "Confirmar anulación" in source
    assert "El motivo de anulación es obligatorio." in source
    assert '"X-CSRF-Token"' in source
    assert "entries.filter(entry => !entry.voided)" in source


def test_void_action_rejects_missing_or_invalid_csrf(admin_client, voided_entry):
    voided_entry.voided = False
    voided_entry.voided_at = None
    voided_entry.void_reason = None
    from app.extensions import db
    db.session.commit()
    url = f"/api/admin/harvest-entries/{voided_entry.id}/void"
    assert admin_client.patch(url, json={"reason": "Motivo válido"}).status_code == 403
    assert admin_client.patch(
        url, json={"reason": "Motivo válido"}, headers={"X-CSRF-Token": "incorrecto"}
    ).status_code == 403


def test_void_from_voids_flow_persists_and_disappears_from_active_list(
    admin_client, voided_entry, app
):
    voided_entry.voided = False
    voided_entry.voided_at = None
    voided_entry.void_reason = None
    from app.extensions import db
    db.session.commit()
    csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
    response = admin_client.patch(
        f"/api/admin/harvest-entries/{voided_entry.id}/void",
        json={"reason": "Motivo confirmado desde Anulaciones"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    db.session.refresh(voided_entry)
    assert voided_entry.voided is True
    assert voided_entry.void_reason == "Motivo confirmado desde Anulaciones"

    local_date = voided_entry.created_at.astimezone(app.config["HARVEST_TIMEZONE"]).date()
    active = admin_client.get(
        "/api/admin/harvest-entries", query_string={"date": local_date.isoformat()}
    ).get_json()["entries"]
    assert all(row["id"] != voided_entry.id or row["voided"] for row in active)
    archived = admin_client.get("/api/voids").get_json()["entries"]
    assert any(row["id"] == voided_entry.id for row in archived)
