from datetime import datetime, time, timezone
from decimal import Decimal

from app.models.harvest_entry import HarvestEntry
from app.models.product import Product
from app.models.worker_assignment import WorkerAssignment
from app.services.harvest_service import register_harvest
from app.services.history_service import get_daily_summary
from app.services.report_service import get_harvest_report
from app.services.scale_config import (
    DEFAULT_BAUDRATE, DEFAULT_BYTESIZE, DEFAULT_HANDSHAKE, DEFAULT_LINE_ENCODING,
    DEFAULT_PARITY, DEFAULT_PROFILE, DEFAULT_STOPBITS, DEFAULT_TERMINATOR,
)
from tests.conftest import make_worker, make_worker_with_assignment


def _product(db_session):
    product = Product(name="Producto fase uno", rate_per_kg=Decimal("7.50"))
    db_session.add(product)
    db_session.flush()
    return product


def test_anonymous_code_creates_one_special_assignment_and_snapshots(db_session, app):
    worker = make_worker(db_session, name=None, slot_number=3)
    product = _product(db_session)
    first, _ = register_harvest(worker.barcode, Decimal("2.000"), product.id)
    second, _ = register_harvest(worker.barcode, Decimal("3.000"), product.id)

    assignments = WorkerAssignment.query.filter_by(worker_id=worker.id).all()
    assert len(assignments) == 1
    assert assignments[0].person_name == "Sin nombre"
    assert first.worker_assignment_id == second.worker_assignment_id == assignments[0].id
    assert first.worker_name_snapshot == "Sin nombre"
    assert first.worker_barcode_snapshot == "TRB000003"
    assert first.worker_slot_number_snapshot == 3
    assert first.product_name_snapshot == product.name
    assert first.weight_kg == Decimal("2.000")
    assert first.amount_mxn == Decimal("15.00")
    assert worker.name is None


def test_anonymous_scan_and_registration_endpoints(client, db_session):
    worker = make_worker(db_session, name=None, slot_number=3)
    product = _product(db_session)
    db_session.commit()
    lookup = client.get("/api/workers/TRB000003")
    assert lookup.status_code == 200
    assert lookup.get_json()["person_name"] == "Sin nombre"
    daily = client.get("/api/harvest/daily/TRB000003")
    assert daily.status_code == 200
    assert daily.get_json()["worker"]["name"] == "Sin nombre"
    response = client.post(
        "/api/harvest/entries",
        json={"barcode": worker.barcode, "weight_kg": "1.500", "product_id": product.id},
    )
    assert response.status_code == 201
    assert response.get_json()["worker"]["name"] == "Sin nombre"


def test_anonymous_movement_visible_in_history_and_reports_only_with_entry(db_session, app):
    tz = app.config["HARVEST_TIMEZONE"]
    worker = make_worker(db_session, name=None, slot_number=3)
    empty_worker = make_worker(db_session, name=None, slot_number=4)
    product = _product(db_session)
    entry, _ = register_harvest(worker.barcode, Decimal("4.000"), product.id)
    now = datetime.now(tz)
    entry.created_at = datetime.combine(now.date(), time(12), tzinfo=tz).astimezone(timezone.utc)
    db_session.commit()

    history = get_daily_summary(now.date(), tz=tz)
    report = get_harvest_report(now.date(), now.date(), tz=tz)
    assert any(row["name"] == "Sin nombre" and row["barcode"] == worker.barcode for row in history["workers"])
    assert any(row["name"] == "Sin nombre" and row["barcode"] == worker.barcode for row in report["workers"])
    assert all(row["barcode"] != empty_worker.barcode for row in history["workers"])
    assert all(row["barcode"] != empty_worker.barcode for row in report["workers"])


def test_recent_quick_void_authorization_csrf_and_persistence(admin_client, client, db_session):
    worker, assignment = make_worker_with_assignment(db_session, name="Fase uno void")
    product = _product(db_session)
    entry = HarvestEntry(
        worker_id=worker.id, worker_assignment_id=assignment.id,
        worker_slot_number_snapshot=worker.slot_number,
        worker_barcode_snapshot=worker.barcode,
        worker_name_snapshot=assignment.person_name,
        product_id=product.id, product_name_snapshot=product.name,
        rate_per_kg_snapshot=product.rate_per_kg, amount_mxn=Decimal("15.00"),
        weight_kg=Decimal("2.000"),
    )
    db_session.add(entry)
    db_session.commit()
    url = f"/api/admin/harvest-entries/{entry.id}/void"
    assert client.patch(url, json={"reason": "Anulación rápida"}).status_code == 401
    assert admin_client.patch(url, json={"reason": "Anulación rápida"}).status_code == 403
    csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
    response = admin_client.patch(
        url, json={"reason": "Anulación rápida"}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 200
    db_session.refresh(entry)
    assert entry.voided and entry.void_reason == "Anulación rápida"
    assert entry.worker_name_snapshot == assignment.person_name
    assert entry.product_name_snapshot == product.name
    assert admin_client.patch(
        url, json={"reason": "Anulación rápida"}, headers={"X-CSRF-Token": csrf}
    ).status_code == 409
    assert any(row["id"] == entry.id for row in admin_client.get("/api/voids").get_json()["entries"])


def test_recent_preview_only_offers_quick_void_to_admin(admin_client, client, db_session):
    worker, assignment = make_worker_with_assignment(db_session, name="Preview fase uno")
    product = _product(db_session)
    entry, _ = register_harvest(worker.barcode, Decimal("1.000"), product.id)
    db_session.commit()
    public = client.get("/api/harvest/recent").get_json()["movements"]
    admin = admin_client.get("/api/harvest/recent").get_json()["movements"]
    assert next(row for row in public if row["id"] == entry.id)["can_void"] is False
    assert next(row for row in admin if row["id"] == entry.id)["can_void"] is True


def test_quick_void_confirmation_can_cancel_without_request(client):
    js = client.get("/static/js/reception.js").get_data(as_text=True)
    confirmation = js.index("window.confirm")
    request = js.index("/api/admin/harvest-entries/", confirmation)
    assert "return" in js[confirmation:request]
    assert 'reason: "Anulación rápida"' in js[request:]


def test_scale_phase1_defaults_do_not_auto_open_port(monkeypatch):
    assert DEFAULT_BAUDRATE == 9600
    assert DEFAULT_BYTESIZE == 8
    assert DEFAULT_PARITY == "N"
    assert DEFAULT_STOPBITS == 1
    assert DEFAULT_HANDSHAKE == "none"
    assert DEFAULT_PROFILE == "generic"
    assert DEFAULT_TERMINATOR == "CR"
    assert DEFAULT_LINE_ENCODING == "ascii"
    monkeypatch.delenv("SCALE_PORT", raising=False)
    from app.services.scale_config import load_scale_config
    try:
        load_scale_config()
    except ValueError as error:
        assert str(error) == "SCALE_PORT is required"
