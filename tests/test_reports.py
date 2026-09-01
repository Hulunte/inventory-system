import pytest
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal

from app.models.worker import Worker
from app.models.harvest_entry import HarvestEntry
from app.extensions import db
from app.services.report_service import get_harvest_report, parse_date


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
    def test_report_with_entries(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w1 = Worker(barcode="RPT001-RPT", name="Ana Rpt Unique")
            w2 = Worker(barcode="RPT002-RPT", name="Bob Rpt Unique")
            db_session.add_all([w1, w2])
            db_session.flush()

            e1 = HarvestEntry(worker_id=w1.id, weight_kg=Decimal("5.000"),
                              created_at=utc_now + timedelta(hours=8))
            e2 = HarvestEntry(worker_id=w1.id, weight_kg=Decimal("3.000"),
                              created_at=utc_now + timedelta(hours=10))
            e3 = HarvestEntry(worker_id=w2.id, weight_kg=Decimal("7.500"),
                              created_at=utc_now + timedelta(hours=9))
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

            w = Worker(barcode="RPT003-INA", name="Inactive Rpt Unique", active=False)
            db_session.add(w)
            db_session.flush()

            e = HarvestEntry(worker_id=w.id, weight_kg=Decimal("4.000"),
                             created_at=utc_now + timedelta(hours=7))
            db_session.add(e)
            db_session.commit()

            result = get_harvest_report(today, today, query_filter="Inactive Rpt Unique", tz=tz)
            barcodes = [wk["barcode"] for wk in result["workers"]]
            assert "RPT003-INA" in barcodes

    def test_report_filter_by_name(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w1 = Worker(barcode="RPT004-NM", name="Carlos Rpt Name")
            w2 = Worker(barcode="RPT005-NM", name="Diana Rpt Name")
            db_session.add_all([w1, w2])
            db_session.flush()

            e1 = HarvestEntry(worker_id=w1.id, weight_kg=Decimal("2.000"),
                              created_at=utc_now + timedelta(hours=8))
            e2 = HarvestEntry(worker_id=w2.id, weight_kg=Decimal("3.000"),
                              created_at=utc_now + timedelta(hours=9))
            db_session.add_all([e1, e2])
            db_session.commit()

            result = get_harvest_report(today, today, query_filter="Carlos Rpt Name", tz=tz)
            assert len(result["workers"]) == 1
            assert result["workers"][0]["barcode"] == "RPT004-NM"

    def test_report_filter_by_barcode(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w1 = Worker(barcode="XYZ800-BC", name="Eve Rpt Barcode")
            w2 = Worker(barcode="XYZ801-BC", name="Frank Rpt Barcode")
            db_session.add_all([w1, w2])
            db_session.flush()

            e1 = HarvestEntry(worker_id=w1.id, weight_kg=Decimal("1.000"),
                              created_at=utc_now + timedelta(hours=8))
            e2 = HarvestEntry(worker_id=w2.id, weight_kg=Decimal("2.000"),
                              created_at=utc_now + timedelta(hours=9))
            db_session.add_all([e1, e2])
            db_session.commit()

            result = get_harvest_report(today, today, query_filter="XYZ800-BC", tz=tz)
            assert len(result["workers"]) == 1
            assert result["workers"][0]["barcode"] == "XYZ800-BC"

    def test_report_preserves_decimal_precision(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w = Worker(barcode="RPT006-PRC", name="Precision Rpt Unique")
            db_session.add(w)
            db_session.flush()

            e = HarvestEntry(worker_id=w.id, weight_kg=Decimal("1.234"),
                             created_at=utc_now + timedelta(hours=8))
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

            w = Worker(barcode="RPT007-FMT", name="Format Rpt Unique")
            db_session.add(w)
            db_session.flush()

            e1 = HarvestEntry(worker_id=w.id, weight_kg=Decimal("5"),
                              created_at=utc_now + timedelta(hours=8))
            e2 = HarvestEntry(worker_id=w.id, weight_kg=Decimal("5.2"),
                              created_at=utc_now + timedelta(hours=9))
            e3 = HarvestEntry(worker_id=w.id, weight_kg=Decimal("5.25"),
                              created_at=utc_now + timedelta(hours=10))
            e4 = HarvestEntry(worker_id=w.id, weight_kg=Decimal("5.250"),
                              created_at=utc_now + timedelta(hours=11))
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

            w = Worker(barcode="RPT008-SD", name="Single Day Rpt")
            db_session.add(w)
            db_session.flush()

            e = HarvestEntry(worker_id=w.id, weight_kg=Decimal("6.000"),
                             created_at=utc_now + timedelta(hours=8))
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

            w = Worker(barcode="RPT009-MD", name="Multi Day Rpt")
            db_session.add(w)
            db_session.flush()

            e1 = HarvestEntry(worker_id=w.id, weight_kg=Decimal("3.000"),
                              created_at=utc_yesterday + timedelta(hours=8))
            e2 = HarvestEntry(worker_id=w.id, weight_kg=Decimal("4.000"),
                              created_at=utc_today + timedelta(hours=9))
            db_session.add_all([e1, e2])
            db_session.commit()

            result = get_harvest_report(yesterday, today, query_filter="Multi Day Rpt", tz=tz)
            assert len(result["workers"]) == 1
            assert result["workers"][0]["entries_count"] == 2
            assert result["workers"][0]["total_weight_kg"] == "7.000"
            assert result["summary"]["total_entries"] == 2
            assert result["summary"]["total_weight_kg"] == "7.000"


class TestReportEndpoints:
    def test_report_endpoint_200(self, client, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w = Worker(barcode="EPT001-RPT", name="Endpoint Rpt")
            db_session.add(w)
            db_session.flush()

            e = HarvestEntry(worker_id=w.id, weight_kg=Decimal("4.500"),
                             created_at=utc_now + timedelta(hours=9))
            db_session.add(e)
            db_session.commit()

            response = client.get(
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

    def test_report_endpoint_missing_both_dates(self, client, db_session):
        response = client.get("/api/reports/harvest")
        assert response.status_code == 400
        data = response.get_json()
        assert "start_date and end_date are required" in data["error"]

    def test_report_endpoint_missing_start_date(self, client, db_session):
        response = client.get("/api/reports/harvest?end_date=2026-08-31")
        assert response.status_code == 400
        data = response.get_json()
        assert "start_date is required" in data["error"]

    def test_report_endpoint_missing_end_date(self, client, db_session):
        response = client.get("/api/reports/harvest?start_date=2026-08-01")
        assert response.status_code == 400
        data = response.get_json()
        assert "end_date is required" in data["error"]

    def test_report_endpoint_invalid_start_date(self, client, db_session):
        response = client.get(
            "/api/reports/harvest?start_date=2026-13-45&end_date=2026-08-31"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid start_date" in data["error"]

    def test_report_endpoint_invalid_end_date(self, client, db_session):
        response = client.get(
            "/api/reports/harvest?start_date=2026-08-01&end_date=not-a-date"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid end_date" in data["error"]

    def test_report_endpoint_start_after_end(self, client, db_session):
        response = client.get(
            "/api/reports/harvest?start_date=2026-08-31&end_date=2026-08-01"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "start_date must not be after end_date" in data["error"]

    def test_report_endpoint_empty_range(self, client, db_session):
        response = client.get(
            "/api/reports/harvest?start_date=2099-01-01&end_date=2099-01-31"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["workers"] == []
        assert data["summary"]["total_workers"] == 0
        assert data["summary"]["total_entries"] == 0
        assert data["summary"]["total_weight_kg"] == "0.000"

    def test_report_endpoint_with_q_filter(self, client, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            today = datetime.now(tz).date()
            start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w1 = Worker(barcode="EPT002-QF", name="Filter Rpt Me")
            w2 = Worker(barcode="EPT003-QF", name="Skip Rpt Me")
            db_session.add_all([w1, w2])
            db_session.flush()

            e1 = HarvestEntry(worker_id=w1.id, weight_kg=Decimal("2.500"),
                              created_at=utc_now + timedelta(hours=8))
            e2 = HarvestEntry(worker_id=w2.id, weight_kg=Decimal("3.000"),
                              created_at=utc_now + timedelta(hours=9))
            db_session.add_all([e1, e2])
            db_session.commit()

            response = client.get(
                f"/api/reports/harvest?start_date={today.isoformat()}"
                f"&end_date={today.isoformat()}&q=Filter+Rpt+Me"
            )
            assert response.status_code == 200
            data = response.get_json()
            assert len(data["workers"]) == 1
            assert data["workers"][0]["name"] == "Filter Rpt Me"

    def test_report_page_renders(self, client, db_session):
        response = client.get("/reports")
        assert response.status_code == 200
        assert b"Reportes de cosecha" in response.data
