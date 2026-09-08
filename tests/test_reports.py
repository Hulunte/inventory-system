import pytest
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal

from app.models.harvest_entry import HarvestEntry
from app.models.product import Product
from app.extensions import db
from app.services.report_service import get_harvest_report, parse_date
from tests.conftest import make_worker, make_worker_with_assignment


class TestParseDate:
    def test_valid_date(self):
        result = parse_date("2026-08-31")
        assert result is not None
        assert result.isoformat() == "2026-08-31"

    def test_invalid_format_slashes(self):
        result = parse_date("31/08/2026")
        assert result is None

    def test_invalid_month(self):
        result = parse_date("2026-13-01")
        assert result is None

    def test_invalid_day(self):
        result = parse_date("2026-02-30")
        assert result is None

    def test_none_input(self):
        result = parse_date(None)
        assert result is None

    def test_empty_string(self):
        result = parse_date("")
        assert result is None


class TestHarvestReport:
    def test_report_includes_worker_and_grand_total_amount(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        today = datetime.now(tz).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=tz).astimezone(timezone.utc)
        worker, assignment = make_worker_with_assignment(db_session, name="Importe visible Rpt")
        product = Product(name="Producto importe visible Rpt", rate_per_kg=Decimal("10.00"))
        db_session.add(product)
        db_session.flush()
        db_session.add_all([
            HarvestEntry(
                worker_id=worker.id, worker_assignment_id=assignment.id,
                worker_slot_number_snapshot=worker.slot_number,
                worker_barcode_snapshot=worker.barcode,
                worker_name_snapshot=assignment.person_name,
                product_id=product.id, product_name_snapshot=product.name,
                rate_per_kg_snapshot=Decimal("10.00"),
                weight_kg=Decimal("2.000"), amount_mxn=Decimal("25.50"),
                created_at=start + timedelta(hours=8),
            ),
            HarvestEntry(
                worker_id=worker.id, worker_assignment_id=assignment.id,
                worker_slot_number_snapshot=worker.slot_number,
                worker_barcode_snapshot=worker.barcode,
                worker_name_snapshot=assignment.person_name,
                product_id=product.id, product_name_snapshot=product.name,
                rate_per_kg_snapshot=Decimal("10.00"),
                weight_kg=Decimal("3.000"), amount_mxn=Decimal("31.25"),
                created_at=start + timedelta(hours=9),
            ),
        ])
        db_session.commit()

        result = get_harvest_report(today, today, query_filter="Importe visible Rpt", tz=tz)
        assert result["workers"][0]["total_amount_mxn"] == "56.75"
        assert result["summary"]["total_amount_mxn"] == "56.75"

    def test_reports_frontend_renders_amount_column(self, client):
        source = client.get("/static/js/reports.js").get_data(as_text=True)
        assert '<th class="num">Importe</th>' in source
        assert "w.total_amount_mxn" in source
        assert "data.summary.total_amount_mxn" in source

    def test_report_with_entries(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w1, a1 = make_worker_with_assignment(db_session, name="Ana Rpt Unique")
            w2, a2 = make_worker_with_assignment(db_session, name="Bob Rpt Unique")

            e1 = HarvestEntry(
                worker_id=w1.id, worker_assignment_id=a1.id,
                worker_slot_number_snapshot=w1.slot_number,
                worker_barcode_snapshot=w1.barcode,
                worker_name_snapshot=a1.person_name,
                weight_kg=Decimal("5.000"),
                created_at=utc_now + timedelta(hours=8),
            )
            e2 = HarvestEntry(
                worker_id=w1.id, worker_assignment_id=a1.id,
                worker_slot_number_snapshot=w1.slot_number,
                worker_barcode_snapshot=w1.barcode,
                worker_name_snapshot=a1.person_name,
                weight_kg=Decimal("3.000"),
                created_at=utc_now + timedelta(hours=10),
            )
            e3 = HarvestEntry(
                worker_id=w2.id, worker_assignment_id=a2.id,
                worker_slot_number_snapshot=w2.slot_number,
                worker_barcode_snapshot=w2.barcode,
                worker_name_snapshot=a2.person_name,
                weight_kg=Decimal("7.500"),
                created_at=utc_now + timedelta(hours=9),
            )
            db_session.add_all([e1, e2, e3])
            db_session.commit()

            result = get_harvest_report(today, today, query_filter="Rpt Unique", tz=tz)
            names = [w["name"] for w in result["workers"]]
            assert "Ana Rpt Unique" in names
            assert "Bob Rpt Unique" in names

            ana = next(w for w in result["workers"] if w["name"] == "Ana Rpt Unique")
            bob = next(w for w in result["workers"] if w["name"] == "Bob Rpt Unique")
            assert ana["entries_count"] == 2
            assert ana["total_weight_kg"] == "8.000"
            assert bob["entries_count"] == 1
            assert bob["total_weight_kg"] == "7.500"

            assert result["summary"]["total_workers"] == 2
            assert result["summary"]["total_entries"] == 3
            assert result["summary"]["total_weight_kg"] == "15.500"

    def test_report_empty_range(self, db_session, app):
        with app.app_context():
            future = date(2099, 12, 31)
            result = get_harvest_report(future, future, tz=app.config["HARVEST_TIMEZONE"])

            assert result["workers"] == []
            assert result["summary"]["total_workers"] == 0
            assert result["summary"]["total_entries"] == 0
            assert result["summary"]["total_weight_kg"] == "0.000"

    def test_report_includes_inactive_workers(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w, a = make_worker_with_assignment(db_session, name="Inactive Rpt Unique", active=False)

            e = HarvestEntry(
                worker_id=w.id, worker_assignment_id=a.id,
                worker_slot_number_snapshot=w.slot_number,
                worker_barcode_snapshot=w.barcode,
                worker_name_snapshot=a.person_name,
                weight_kg=Decimal("4.000"),
                created_at=utc_now + timedelta(hours=7),
            )
            db_session.add(e)
            db_session.commit()

            result = get_harvest_report(today, today, query_filter="Inactive Rpt Unique", tz=tz)
            barcodes = [wk["barcode"] for wk in result["workers"]]
            assert w.barcode in barcodes

    def test_report_filter_by_name(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w1, a1 = make_worker_with_assignment(db_session, name="Carlos Rpt Name")
            w2, a2 = make_worker_with_assignment(db_session, name="Diana Rpt Name")

            e1 = HarvestEntry(
                worker_id=w1.id, worker_assignment_id=a1.id,
                worker_slot_number_snapshot=w1.slot_number,
                worker_barcode_snapshot=w1.barcode,
                worker_name_snapshot=a1.person_name,
                weight_kg=Decimal("2.000"),
                created_at=utc_now + timedelta(hours=8),
            )
            e2 = HarvestEntry(
                worker_id=w2.id, worker_assignment_id=a2.id,
                worker_slot_number_snapshot=w2.slot_number,
                worker_barcode_snapshot=w2.barcode,
                worker_name_snapshot=a2.person_name,
                weight_kg=Decimal("3.000"),
                created_at=utc_now + timedelta(hours=9),
            )
            db_session.add_all([e1, e2])
            db_session.commit()

            result = get_harvest_report(today, today, query_filter="Carlos Rpt Name", tz=tz)
            assert len(result["workers"]) == 1
            assert result["workers"][0]["barcode"] == w1.barcode

    def test_report_filter_by_barcode(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w1, a1 = make_worker_with_assignment(db_session, name="Eve Rpt Barcode")
            w2, a2 = make_worker_with_assignment(db_session, name="Frank Rpt Barcode")

            e1 = HarvestEntry(
                worker_id=w1.id, worker_assignment_id=a1.id,
                worker_slot_number_snapshot=w1.slot_number,
                worker_barcode_snapshot=w1.barcode,
                worker_name_snapshot=a1.person_name,
                weight_kg=Decimal("1.000"),
                created_at=utc_now + timedelta(hours=8),
            )
            e2 = HarvestEntry(
                worker_id=w2.id, worker_assignment_id=a2.id,
                worker_slot_number_snapshot=w2.slot_number,
                worker_barcode_snapshot=w2.barcode,
                worker_name_snapshot=a2.person_name,
                weight_kg=Decimal("2.000"),
                created_at=utc_now + timedelta(hours=9),
            )
            db_session.add_all([e1, e2])
            db_session.commit()

            result = get_harvest_report(today, today, query_filter=w1.barcode, tz=tz)
            assert len(result["workers"]) == 1
            assert result["workers"][0]["barcode"] == w1.barcode

    def test_report_preserves_decimal_precision(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w, a = make_worker_with_assignment(db_session, name="Precision Rpt Unique")

            e = HarvestEntry(
                worker_id=w.id, worker_assignment_id=a.id,
                worker_slot_number_snapshot=w.slot_number,
                worker_barcode_snapshot=w.barcode,
                worker_name_snapshot=a.person_name,
                weight_kg=Decimal("1.234"),
                created_at=utc_now + timedelta(hours=8),
            )
            db_session.add(e)
            db_session.commit()

            result = get_harvest_report(today, today, query_filter="Precision Rpt Unique", tz=tz)
            assert result["workers"][0]["total_weight_kg"] == "1.234"
            assert result["summary"]["total_weight_kg"] == "1.234"

    def test_decimal_formatting_three_places(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w, a = make_worker_with_assignment(db_session, name="Format Rpt Unique")

            e1 = HarvestEntry(
                worker_id=w.id, worker_assignment_id=a.id,
                worker_slot_number_snapshot=w.slot_number,
                worker_barcode_snapshot=w.barcode,
                worker_name_snapshot=a.person_name,
                weight_kg=Decimal("5"),
                created_at=utc_now + timedelta(hours=8),
            )
            e2 = HarvestEntry(
                worker_id=w.id, worker_assignment_id=a.id,
                worker_slot_number_snapshot=w.slot_number,
                worker_barcode_snapshot=w.barcode,
                worker_name_snapshot=a.person_name,
                weight_kg=Decimal("5.2"),
                created_at=utc_now + timedelta(hours=9),
            )
            e3 = HarvestEntry(
                worker_id=w.id, worker_assignment_id=a.id,
                worker_slot_number_snapshot=w.slot_number,
                worker_barcode_snapshot=w.barcode,
                worker_name_snapshot=a.person_name,
                weight_kg=Decimal("5.25"),
                created_at=utc_now + timedelta(hours=10),
            )
            e4 = HarvestEntry(
                worker_id=w.id, worker_assignment_id=a.id,
                worker_slot_number_snapshot=w.slot_number,
                worker_barcode_snapshot=w.barcode,
                worker_name_snapshot=a.person_name,
                weight_kg=Decimal("5.250"),
                created_at=utc_now + timedelta(hours=11),
            )
            db_session.add_all([e1, e2, e3, e4])
            db_session.commit()

            result = get_harvest_report(today, today, query_filter="Format Rpt Unique", tz=tz)
            worker = result["workers"][0]
            assert worker["total_weight_kg"] == "20.700"
            assert worker["entries_count"] == 4
            assert result["summary"]["total_weight_kg"] == "20.700"

    def test_report_single_day_range(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w, a = make_worker_with_assignment(db_session, name="Single Day Rpt")

            e = HarvestEntry(
                worker_id=w.id, worker_assignment_id=a.id,
                worker_slot_number_snapshot=w.slot_number,
                worker_barcode_snapshot=w.barcode,
                worker_name_snapshot=a.person_name,
                weight_kg=Decimal("6.000"),
                created_at=utc_now + timedelta(hours=8),
            )
            db_session.add(e)
            db_session.commit()

            result = get_harvest_report(today, today, query_filter="Single Day Rpt", tz=tz)
            assert len(result["workers"]) == 1
            assert result["workers"][0]["total_weight_kg"] == "6.000"

    def test_report_multi_day_range(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            yesterday = today - timedelta(days=1)
            start_yesterday = datetime.combine(yesterday, datetime.min.time(), tzinfo=tz)
            utc_yesterday = start_yesterday.astimezone(timezone.utc)

            start_today = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_today = start_today.astimezone(timezone.utc)

            w, a = make_worker_with_assignment(db_session, name="Multi Day Rpt")

            e1 = HarvestEntry(
                worker_id=w.id, worker_assignment_id=a.id,
                worker_slot_number_snapshot=w.slot_number,
                worker_barcode_snapshot=w.barcode,
                worker_name_snapshot=a.person_name,
                weight_kg=Decimal("3.000"),
                created_at=utc_yesterday + timedelta(hours=8),
            )
            e2 = HarvestEntry(
                worker_id=w.id, worker_assignment_id=a.id,
                worker_slot_number_snapshot=w.slot_number,
                worker_barcode_snapshot=w.barcode,
                worker_name_snapshot=a.person_name,
                weight_kg=Decimal("4.000"),
                created_at=utc_today + timedelta(hours=9),
            )
            db_session.add_all([e1, e2])
            db_session.commit()

            result = get_harvest_report(yesterday, today, query_filter="Multi Day Rpt", tz=tz)
            assert len(result["workers"]) == 1
            assert result["workers"][0]["entries_count"] == 2
            assert result["workers"][0]["total_weight_kg"] == "7.000"
            assert result["summary"]["total_entries"] == 2
            assert result["summary"]["total_weight_kg"] == "7.000"


class TestReportEndpoints:
    def test_report_endpoint_200(self, admin_client, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w, a = make_worker_with_assignment(db_session, name="Endpoint Rpt")

            e = HarvestEntry(
                worker_id=w.id, worker_assignment_id=a.id,
                worker_slot_number_snapshot=w.slot_number,
                worker_barcode_snapshot=w.barcode,
                worker_name_snapshot=a.person_name,
                weight_kg=Decimal("4.500"),
                created_at=utc_now + timedelta(hours=9),
            )
            db_session.add(e)
            db_session.commit()

            response = admin_client.get(
                f"/api/reports/harvest?start_date={today.isoformat()}"
                f"&end_date={today.isoformat()}&q=Endpoint+Rpt"
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["start_date"] == today.isoformat()
            assert data["end_date"] == today.isoformat()
            assert data["summary"]["total_entries"] == 1
            assert data["summary"]["total_weight_kg"] == "4.500"
            assert len(data["workers"]) == 1

    def test_report_endpoint_missing_both_dates(self, admin_client, db_session):
        response = admin_client.get("/api/reports/harvest")
        assert response.status_code == 400
        data = response.get_json()
        assert "start_date and end_date are required" in data["error"]

    def test_report_endpoint_missing_start_date(self, admin_client, db_session):
        response = admin_client.get("/api/reports/harvest?end_date=2026-08-31")
        assert response.status_code == 400
        data = response.get_json()
        assert "start_date is required" in data["error"]

    def test_report_endpoint_missing_end_date(self, admin_client, db_session):
        response = admin_client.get("/api/reports/harvest?start_date=2026-08-01")
        assert response.status_code == 400
        data = response.get_json()
        assert "end_date is required" in data["error"]

    def test_report_endpoint_invalid_start_date(self, admin_client, db_session):
        response = admin_client.get(
            "/api/reports/harvest?start_date=2026-13-45&end_date=2026-08-31"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid start_date" in data["error"]

    def test_report_endpoint_invalid_end_date(self, admin_client, db_session):
        response = admin_client.get(
            "/api/reports/harvest?start_date=2026-08-01&end_date=not-a-date"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid end_date" in data["error"]

    def test_report_endpoint_start_after_end(self, admin_client, db_session):
        response = admin_client.get(
            "/api/reports/harvest?start_date=2026-08-31&end_date=2026-08-01"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "start_date must not be after end_date" in data["error"]

    def test_report_endpoint_empty_range(self, admin_client, db_session):
        response = admin_client.get(
            "/api/reports/harvest?start_date=2099-01-01&end_date=2099-01-31"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["workers"] == []
        assert data["summary"]["total_workers"] == 0
        assert data["summary"]["total_entries"] == 0
        assert data["summary"]["total_weight_kg"] == "0.000"

    def test_report_endpoint_with_q_filter(self, admin_client, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w1, a1 = make_worker_with_assignment(db_session, name="Filter Rpt Me")
            w2, a2 = make_worker_with_assignment(db_session, name="Skip Rpt Me")

            e1 = HarvestEntry(
                worker_id=w1.id, worker_assignment_id=a1.id,
                worker_slot_number_snapshot=w1.slot_number,
                worker_barcode_snapshot=w1.barcode,
                worker_name_snapshot=a1.person_name,
                weight_kg=Decimal("2.500"),
                created_at=utc_now + timedelta(hours=8),
            )
            e2 = HarvestEntry(
                worker_id=w2.id, worker_assignment_id=a2.id,
                worker_slot_number_snapshot=w2.slot_number,
                worker_barcode_snapshot=w2.barcode,
                worker_name_snapshot=a2.person_name,
                weight_kg=Decimal("3.000"),
                created_at=utc_now + timedelta(hours=9),
            )
            db_session.add_all([e1, e2])
            db_session.commit()

            response = admin_client.get(
                f"/api/reports/harvest?start_date={today.isoformat()}"
                f"&end_date={today.isoformat()}&q=Filter+Rpt+Me"
            )
            assert response.status_code == 200
            data = response.get_json()
            assert len(data["workers"]) == 1
            assert data["workers"][0]["name"] == "Filter Rpt Me"

    def test_report_page_renders(self, admin_client, db_session):
        response = admin_client.get("/reports")
        assert response.status_code == 200
        assert b"Reportes de cosecha" in response.data

    def test_report_page_operational_today(self, admin_client, monkeypatch):
        monkeypatch.setattr("app.routes.views._operational_today", lambda: date(2026, 6, 17))
        response = admin_client.get("/reports")
        assert response.status_code == 200
        html = response.data.decode()
        assert 'REPORTS_CONFIG' in html
        assert 'operationalToday: "2026-06-17"' in html
        assert 'currentWeekStart: "2026-06-15"' in html
        assert 'currentWeekEnd: "2026-06-21"' in html
        assert 'previousWeekStart: "2026-06-08"' in html
        assert 'previousWeekEnd: "2026-06-14"' in html
