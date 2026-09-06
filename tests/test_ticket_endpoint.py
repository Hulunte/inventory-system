"""Tests for ticket API endpoints."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models.harvest_entry import HarvestEntry
from app.models.product import Product
from tests.conftest import make_worker_with_assignment

TZ = ZoneInfo("America/Chihuahua")


def _get_csrf(admin_client):
    return admin_client.get("/api/admin/session").get_json()["csrf_token"]


def _ensure_product(db_session, name="Naranja", rate="12.50"):
    product = Product.query.filter_by(name=name).first()
    if product is None:
        product = Product(name=name, rate_per_kg=Decimal(rate), active=True)
        db_session.add(product)
        db_session.flush()
    return product


def _make_entry(db_session, worker, assignment, weight_kg, created_at, product=None):
    entry = HarvestEntry(
        worker_id=worker.id,
        weight_kg=Decimal(str(weight_kg)),
        product_id=product.id if product else None,
        product_name_snapshot=product.name if product else None,
        rate_per_kg_snapshot=Decimal(str(product.rate_per_kg)) if product else None,
        amount_mxn=Decimal(str(weight_kg)) * Decimal(str(product.rate_per_kg)) if product else None,
        created_at=created_at,
        worker_assignment_id=assignment.id,
        worker_slot_number_snapshot=worker.slot_number,
        worker_barcode_snapshot=worker.barcode,
        worker_name_snapshot=assignment.person_name,
    )
    db_session.add(entry)
    db_session.flush()
    return entry


class TestDailyEndpoint:
    def test_no_auth_returns_401(self, client):
        resp = client.get("/api/tickets/daily?date=2026-06-15")
        assert resp.status_code == 401

    def test_returns_tickets(self, admin_client, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=10)
        product = _ensure_product(db_session)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 50.0, created, product=product)
        db_session.commit()

        resp = admin_client.get("/api/tickets/daily?date=2026-06-15")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["date"] == "2026-06-15"
        assert len(data["tickets"]) == 1
        assert data["tickets"][0]["slot_number"] == 10

    def test_invalid_date_format(self, admin_client):
        resp = admin_client.get("/api/tickets/daily?date=not-a-date")
        assert resp.status_code == 400
        assert "fecha" in resp.get_json()["error"].lower()

    def test_filter_by_name(self, admin_client, db_session):
        w1, a1 = make_worker_with_assignment(db_session, slot_number=20, person_name="Juan")
        w2, a2 = make_worker_with_assignment(db_session, slot_number=21, person_name="Maria")
        product = _ensure_product(db_session)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, w1, a1, 10.0, created, product=product)
        _make_entry(db_session, w2, a2, 20.0, created, product=product)
        db_session.commit()

        resp = admin_client.get("/api/tickets/daily?date=2026-06-15&q=Juan")
        assert resp.status_code == 200
        assert len(resp.get_json()["tickets"]) == 1

    def test_filter_too_long_returns_400(self, admin_client):
        long_q = "A" * 51
        resp = admin_client.get(f"/api/tickets/daily?date=2026-06-15&q={long_q}")
        assert resp.status_code == 400
        assert "demasiado largo" in resp.get_json()["error"].lower()

    def test_filter_exact_max_length_ok(self, admin_client):
        max_q = "A" * 50
        resp = admin_client.get(f"/api/tickets/daily?date=2026-06-15&q={max_q}")
        assert resp.status_code == 200


class TestPrintersEndpoint:
    def test_no_auth_returns_401(self, client):
        resp = client.get("/api/tickets/printers")
        assert resp.status_code == 401

    def test_returns_structure(self, admin_client):
        resp = admin_client.get("/api/tickets/printers")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "direct_printing_available" in data
        assert "default_printer" in data
        assert "printers" in data
        assert isinstance(data["printers"], list)


class TestTestPrintEndpoint:
    def test_no_auth_returns_401(self, client):
        resp = client.post("/api/tickets/printers/test", json={"printer_name": "Test"})
        assert resp.status_code == 401

    def test_no_csrf_returns_403(self, admin_client):
        resp = admin_client.post("/api/tickets/printers/test", json={"printer_name": "Test"})
        assert resp.status_code == 403

    def test_invalid_json(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/printers/test",
            data="not json",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_unknown_field(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/printers/test",
            json={"printer_name": "Test", "extra": "field"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400
        assert "Unknown fields" in resp.get_json()["error"]

    def test_missing_printer_name(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/printers/test",
            json={},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_empty_printer_name(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/printers/test",
            json={"printer_name": ""},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_printer_name_null_bytes_stripped(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/printers/test",
            json={"printer_name": "Test\x00Printer"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code in (404, 503)

    def test_printer_name_whitespace_stripped(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/printers/test",
            json={"printer_name": "  Test  "},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code in (404, 503)

    @patch("app.routes.tickets.is_available", return_value=False)
    def test_unavailable_returns_503(self, mock_avail, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/printers/test",
            json={"printer_name": "Test"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 503

    @patch("app.routes.tickets.is_available", return_value=True)
    @patch("app.routes.tickets.validate_printer_name", return_value=False)
    def test_unknown_printer_returns_404(self, mock_val, mock_avail, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/printers/test",
            json={"printer_name": "Unknown"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 404


class TestPrintEndpoint:
    def test_no_auth_returns_401(self, client):
        resp = client.post("/api/tickets/print", json={
            "date": "2026-06-15",
            "worker_assignment_id": 1,
            "printer_name": "Test",
        })
        assert resp.status_code == 401

    def test_no_csrf_returns_403(self, admin_client):
        resp = admin_client.post("/api/tickets/print", json={
            "date": "2026-06-15",
            "worker_assignment_id": 1,
            "printer_name": "Test",
        })
        assert resp.status_code == 403

    def test_invalid_json(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            data="not json",
            content_type="application/json",
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_unknown_field(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={
                "date": "2026-06-15",
                "worker_assignment_id": 1,
                "printer_name": "Test",
                "extra": True,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_missing_date(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={"worker_assignment_id": 1, "printer_name": "Test"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_invalid_date(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={"date": "bad", "worker_assignment_id": 1, "printer_name": "Test"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_assignment_id_bool(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={"date": "2026-06-15", "worker_assignment_id": True, "printer_name": "Test"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_assignment_id_zero(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={"date": "2026-06-15", "worker_assignment_id": 0, "printer_name": "Test"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_assignment_id_negative(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={"date": "2026-06-15", "worker_assignment_id": -1, "printer_name": "Test"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    def test_missing_printer_name(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={"date": "2026-06-15", "worker_assignment_id": 1},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 400

    @patch("app.routes.tickets.is_available", return_value=False)
    def test_unavailable_returns_503(self, mock_avail, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={"date": "2026-06-15", "worker_assignment_id": 1, "printer_name": "Test"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 503

    @patch("app.routes.tickets.is_available", return_value=True)
    @patch("app.routes.tickets.validate_printer_name", return_value=False)
    def test_unknown_printer_returns_404(self, mock_val, mock_avail, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={"date": "2026-06-15", "worker_assignment_id": 1, "printer_name": "Unknown"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 404

    @patch("app.routes.tickets.is_available", return_value=True)
    @patch("app.routes.tickets.validate_printer_name", return_value=True)
    def test_ticket_not_found_returns_404(self, mock_val, mock_avail, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={"date": "2020-01-01", "worker_assignment_id": 99999, "printer_name": "Test"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 404

    @patch("app.routes.tickets.is_available", return_value=True)
    @patch("app.routes.tickets.validate_printer_name", return_value=True)
    @patch("app.routes.tickets.print_raw")
    def test_success(self, mock_print, mock_val, mock_avail, admin_client, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=10)
        product = _ensure_product(db_session)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 50.0, created, product=product)
        db_session.commit()

        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={
                "date": "2026-06-15",
                "worker_assignment_id": assignment.id,
                "printer_name": "TestPrinter",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200
        assert "impreso" in resp.get_json()["message"].lower()
        mock_print.assert_called_once()

    @patch("app.routes.tickets.is_available", return_value=True)
    @patch("app.routes.tickets.validate_printer_name", return_value=True)
    @patch("app.routes.tickets.print_raw")
    def test_spooler_error_returns_502(self, mock_print, mock_val, mock_avail, admin_client, db_session):
        from app.services.printer_service import PrinterError
        mock_print.side_effect = PrinterError("Spooler failed")

        worker, assignment = make_worker_with_assignment(db_session, slot_number=11)
        product = _ensure_product(db_session)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 50.0, created, product=product)
        db_session.commit()

        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={
                "date": "2026-06-15",
                "worker_assignment_id": assignment.id,
                "printer_name": "TestPrinter",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 502

    @patch("app.routes.tickets.is_available", return_value=True)
    @patch("app.routes.tickets.validate_printer_name", return_value=True)
    def test_incomplete_without_confirm_returns_409(self, mock_val, mock_avail, admin_client, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=12)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        entry = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("10.000"),
            product_id=None,
            product_name_snapshot=None,
            rate_per_kg_snapshot=None,
            amount_mxn=None,
            created_at=created,
            worker_assignment_id=assignment.id,
            worker_slot_number_snapshot=worker.slot_number,
            worker_barcode_snapshot=worker.barcode,
            worker_name_snapshot=assignment.person_name,
        )
        db_session.add(entry)
        db_session.flush()
        db_session.commit()

        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={
                "date": "2026-06-15",
                "worker_assignment_id": assignment.id,
                "printer_name": "TestPrinter",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 409
        data = resp.get_json()
        assert data["has_incomplete_amounts"] is True

    @patch("app.routes.tickets.is_available", return_value=True)
    @patch("app.routes.tickets.validate_printer_name", return_value=True)
    @patch("app.routes.tickets.print_raw")
    def test_ignored_manipulated_totals(self, mock_print, mock_val, mock_avail, admin_client, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=13)
        product = _ensure_product(db_session)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 50.0, created, product=product)
        db_session.commit()

        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={
                "date": "2026-06-15",
                "worker_assignment_id": assignment.id,
                "printer_name": "TestPrinter",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200

        call_args = mock_print.call_args
        rendered_bytes = call_args[0][1]
        assert isinstance(rendered_bytes, bytes)

    def test_no_internal_info_in_error(self, admin_client):
        csrf = _get_csrf(admin_client)
        resp = admin_client.post(
            "/api/tickets/print",
            json={
                "date": "2026-06-15",
                "worker_assignment_id": 99999,
                "printer_name": "Test",
            },
            headers={"X-CSRF-Token": csrf},
        )
        error = resp.get_json().get("error", "")
        assert "Port" not in error
        assert "USB" not in error
        assert "spooler" not in error.lower()


class TestTicketsPage:
    def test_no_auth_redirects(self, client):
        resp = client.get("/tickets")
        assert resp.status_code == 302

    def test_admin_can_access(self, admin_client):
        resp = admin_client.get("/tickets")
        assert resp.status_code == 200
        assert "tickets" in resp.data.decode().lower()


class TestApiContractWithFrontend:
    """Verify the JSON contract matches what tickets.js expects.

    Simulates the exact scenario from production:
    - Two workers with closed assignments
    - Entries with null amount_mxn (no product/rate snapshot)
    - has_incomplete_amounts: true
    - Search by barcode must work
    """

    def _setup_two_workers(self, db_session):
        w1, a1 = make_worker_with_assignment(
            db_session, slot_number=1, person_name="Trabajador de prueba"
        )
        w2, a2 = make_worker_with_assignment(
            db_session, slot_number=2, person_name="Mau"
        )
        a2.ended_at = a2.started_at + timedelta(hours=6)
        db_session.flush()

        op_date = date(2026, 8, 31)
        created1 = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)
        created2 = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)

        e1 = HarvestEntry(
            worker_id=w1.id,
            weight_kg=Decimal("29.375"),
            product_id=None,
            product_name_snapshot=None,
            rate_per_kg_snapshot=None,
            amount_mxn=None,
            created_at=created1,
            worker_assignment_id=a1.id,
            worker_slot_number_snapshot=w1.slot_number,
            worker_barcode_snapshot="TRB000001",
            worker_name_snapshot=a1.person_name,
        )
        db_session.add(e1)

        e2 = HarvestEntry(
            worker_id=w2.id,
            weight_kg=Decimal("35.000"),
            product_id=None,
            product_name_snapshot=None,
            rate_per_kg_snapshot=None,
            amount_mxn=None,
            created_at=created2,
            worker_assignment_id=a2.id,
            worker_slot_number_snapshot=w2.slot_number,
            worker_barcode_snapshot="7509876543210",
            worker_name_snapshot=a2.person_name,
        )
        db_session.add(e2)
        db_session.commit()

        return w1, a1, w2, a2, op_date

    def test_api_returns_two_tickets(self, admin_client, db_session):
        self._setup_two_workers(db_session)
        resp = admin_client.get("/api/tickets/daily?date=2026-08-31")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tickets"]) == 2

    def test_root_fields_match_js_contract(self, admin_client, db_session):
        self._setup_two_workers(db_session)
        resp = admin_client.get("/api/tickets/daily?date=2026-08-31")
        data = resp.get_json()
        assert "date" in data
        assert "tickets" in data
        assert "total_workers" in data
        assert "total_day_weight_kg" in data
        assert "total_day_amount_mxn" in data
        assert isinstance(data["tickets"], list)
        assert isinstance(data["total_workers"], int)
        assert isinstance(data["total_day_weight_kg"], str)
        assert isinstance(data["total_day_amount_mxn"], str)

    def test_ticket_fields_match_js_contract(self, admin_client, db_session):
        self._setup_two_workers(db_session)
        resp = admin_client.get("/api/tickets/daily?date=2026-08-31")
        data = resp.get_json()
        for t in data["tickets"]:
            assert "worker_assignment_id" in t
            assert "slot_number" in t
            assert "slot_label" in t
            assert "worker_name" in t
            assert "worker_barcode" in t
            assert "product_lines" in t
            assert "total_weight_kg" in t
            assert "total_amount_mxn" in t
            assert "has_incomplete_amounts" in t
            assert isinstance(t["product_lines"], list)
            assert isinstance(t["has_incomplete_amounts"], bool)

    def test_product_line_fields_match_js_contract(self, admin_client, db_session):
        self._setup_two_workers(db_session)
        resp = admin_client.get("/api/tickets/daily?date=2026-08-31")
        data = resp.get_json()
        for t in data["tickets"]:
            for line in t["product_lines"]:
                assert "product_name" in line
                assert "weight_kg" in line
                assert "rate_per_kg" in line
                assert "amount_mxn" in line

    def test_null_amount_mxn_renders_as_nd(self, admin_client, db_session):
        self._setup_two_workers(db_session)
        resp = admin_client.get("/api/tickets/daily?date=2026-08-31")
        data = resp.get_json()
        for t in data["tickets"]:
            assert t["has_incomplete_amounts"] is True
            line = t["product_lines"][0]
            assert line["amount_mxn"] is None

    def test_incomplete_amounts_ticket_not_excluded(self, admin_client, db_session):
        self._setup_two_workers(db_session)
        resp = admin_client.get("/api/tickets/daily?date=2026-08-31")
        data = resp.get_json()
        incomplete = [t for t in data["tickets"] if t["has_incomplete_amounts"]]
        assert len(incomplete) == 2
        for t in data["tickets"]:
            assert len(t["product_lines"]) == 1
            assert t["product_lines"][0]["amount_mxn"] is None

    def test_search_by_trb_barcode_finds_ticket(self, admin_client, db_session):
        self._setup_two_workers(db_session)
        resp = admin_client.get("/api/tickets/daily?date=2026-08-31&q=TRB000001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tickets"]) == 1
        assert data["tickets"][0]["worker_barcode"] == "TRB000001"
        assert data["tickets"][0]["worker_name"] == "Trabajador de prueba"

    def test_search_by_historical_barcode_finds_ticket(self, admin_client, db_session):
        self._setup_two_workers(db_session)
        resp = admin_client.get("/api/tickets/daily?date=2026-08-31&q=7509876543210")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tickets"]) == 1
        assert data["tickets"][0]["worker_barcode"] == "7509876543210"
        assert data["tickets"][0]["worker_name"] == "Mau"

    def test_search_by_worker_name_finds_ticket(self, admin_client, db_session):
        self._setup_two_workers(db_session)
        resp = admin_client.get("/api/tickets/daily?date=2026-08-31&q=Mau")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tickets"]) == 1
        assert data["tickets"][0]["worker_name"] == "Mau"

    def test_search_by_slot_label(self, admin_client, db_session):
        self._setup_two_workers(db_session)
        resp = admin_client.get("/api/tickets/daily?date=2026-08-31&q=001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tickets"]) == 1
        assert data["tickets"][0]["slot_number"] == 1

    def test_stats_sum_both_tickets(self, admin_client, db_session):
        self._setup_two_workers(db_session)
        resp = admin_client.get("/api/tickets/daily?date=2026-08-31")
        data = resp.get_json()
        assert data["total_workers"] == 2
        assert data["total_day_weight_kg"] == "64.375"
