import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.harvest_entry import HarvestEntry
from app.services.history_service import (
    get_daily_summary,
    get_worker_entries,
    parse_date,
)
from tests.conftest import make_worker, make_worker_with_assignment


def _make_aware(dt_str, tz):
    naive = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    return naive.replace(tzinfo=tz)


def _make_entry(db_session, worker, assignment, weight_kg, created_at):
    entry = HarvestEntry(
        worker_id=worker.id,
        weight_kg=weight_kg,
        created_at=created_at,
        worker_assignment_id=assignment.id,
        worker_slot_number_snapshot=worker.slot_number,
        worker_barcode_snapshot=worker.barcode,
        worker_name_snapshot=assignment.person_name,
    )
    db_session.add(entry)
    return entry


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


class TestDailySummary:
    def test_summary_with_entries(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import time as dt_time

            today = datetime.now(tz).date()
            start = datetime.combine(today, dt_time.min, tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w1, a1 = make_worker_with_assignment(db_session, None, name="Ana Lopez Sum")
            w2, a2 = make_worker_with_assignment(db_session, None, name="Bob Smith Sum")

            _make_entry(db_session, w1, a1, Decimal("5.000"), utc_now + timedelta(hours=8))
            _make_entry(db_session, w1, a1, Decimal("3.000"), utc_now + timedelta(hours=10))
            _make_entry(db_session, w2, a2, Decimal("7.500"), utc_now + timedelta(hours=9))
            db_session.commit()

            result = get_daily_summary(today, query_filter="Sum", tz=tz)
            names = [w["name"] for w in result["workers"]]
            assert "Ana Lopez Sum" in names
            assert "Bob Smith Sum" in names

            ana = next(w for w in result["workers"] if w["name"] == "Ana Lopez Sum")
            bob = next(w for w in result["workers"] if w["name"] == "Bob Smith Sum")
            assert ana["entries_count"] == 2
            assert ana["total_weight_kg"] == "8.000"
            assert bob["entries_count"] == 1
            assert bob["total_weight_kg"] == "7.500"
            assert result["summary"]["total_entries"] == 3
            assert result["summary"]["total_weight_kg"] == "15.500"

    def test_summary_empty_date(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import date

            future_date = date(2099, 12, 31)
            result = get_daily_summary(future_date, tz=tz)

            assert len(result["workers"]) == 0
            assert result["summary"]["total_entries"] == 0
            assert result["summary"]["total_weight_kg"] == "0.000"

    def test_summary_includes_inactive_workers(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import time as dt_time

            today = datetime.now(tz).date()
            start = datetime.combine(today, dt_time.min, tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w, a = make_worker_with_assignment(db_session, None, name="Inactive History X", active=False)

            _make_entry(db_session, w, a, Decimal("4.000"), utc_now + timedelta(hours=7))
            db_session.commit()

            result = get_daily_summary(today, query_filter="Inactive History X", tz=tz)
            barcodes = [wk["barcode"] for wk in result["workers"]]
            assert w.barcode in barcodes

    def test_summary_search_filter_by_name(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import time as dt_time

            today = datetime.now(tz).date()
            start = datetime.combine(today, dt_time.min, tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w1, a1 = make_worker_with_assignment(db_session, None, name="Carlos Diaz Unique")
            w2, a2 = make_worker_with_assignment(db_session, None, name="Diana Ross Unique")

            _make_entry(db_session, w1, a1, Decimal("2.000"), utc_now + timedelta(hours=8))
            _make_entry(db_session, w2, a2, Decimal("3.000"), utc_now + timedelta(hours=9))
            db_session.commit()

            result = get_daily_summary(today, query_filter="Carlos Diaz Unique", tz=tz)
            assert len(result["workers"]) == 1
            assert result["workers"][0]["barcode"] == w1.barcode

    def test_summary_search_filter_by_barcode(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import time as dt_time

            today = datetime.now(tz).date()
            start = datetime.combine(today, dt_time.min, tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w1, a1 = make_worker_with_assignment(db_session, None, name="Eve Adams BC")
            w2, a2 = make_worker_with_assignment(db_session, None, name="Frank White BC")

            _make_entry(db_session, w1, a1, Decimal("1.000"), utc_now + timedelta(hours=8))
            _make_entry(db_session, w2, a2, Decimal("2.000"), utc_now + timedelta(hours=9))
            db_session.commit()

            result = get_daily_summary(today, query_filter=w1.barcode, tz=tz)
            assert len(result["workers"]) == 1
            assert result["workers"][0]["barcode"] == w1.barcode

    def test_summary_preserves_decimal_precision(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import time as dt_time

            today = datetime.now(tz).date()
            start = datetime.combine(today, dt_time.min, tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w, a = make_worker_with_assignment(db_session, None, name="Precision Test Unique")

            _make_entry(db_session, w, a, Decimal("1.234"), utc_now + timedelta(hours=8))
            db_session.commit()

            result = get_daily_summary(today, query_filter="Precision Test Unique", tz=tz)
            assert result["workers"][0]["total_weight_kg"] == "1.234"
            assert result["summary"]["total_weight_kg"] == "1.234"


class TestWorkerEntries:
    def test_worker_entries_detail(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import time as dt_time

            today = datetime.now(tz).date()
            start = datetime.combine(today, dt_time.min, tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w, a = make_worker_with_assignment(db_session, None, name="Detail Worker Unique")

            _make_entry(db_session, w, a, Decimal("5.250"), utc_now + timedelta(hours=8, minutes=15))
            _make_entry(db_session, w, a, Decimal("6.000"), utc_now + timedelta(hours=10, minutes=30))
            db_session.commit()

            entries = get_worker_entries(a.id, today, tz)
            assert len(entries) == 2
            assert entries[0].weight_kg == Decimal("5.250")
            assert entries[1].weight_kg == Decimal("6.000")

    def test_worker_entries_empty(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import date

            w, a = make_worker_with_assignment(db_session, None, name="No Entries Worker Unique")

            entries = get_worker_entries(a.id, date(2099, 1, 1), tz)
            assert len(entries) == 0

    def test_worker_entries_inactive_worker(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import time as dt_time

            today = datetime.now(tz).date()
            start = datetime.combine(today, dt_time.min, tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w, a = make_worker_with_assignment(db_session, None, name="Inactive Entries Unique", active=False)

            _make_entry(db_session, w, a, Decimal("3.000"), utc_now + timedelta(hours=7))
            db_session.commit()

            entries = get_worker_entries(a.id, today, tz)
            assert len(entries) == 1

    def test_worker_entries_time_in_operational_timezone(self, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import time as dt_time

            today = datetime.now(tz).date()
            start = datetime.combine(today, dt_time.min, tzinfo=tz)
            utc_8am = start.astimezone(timezone.utc) + timedelta(hours=8)

            w, a = make_worker_with_assignment(db_session, None, name="TZ Test Unique")

            _make_entry(db_session, w, a, Decimal("1.000"), utc_8am)
            db_session.commit()

            entries = get_worker_entries(a.id, today, tz)
            assert len(entries) == 1

            local_time = entries[0].created_at.astimezone(tz)
            assert local_time.hour == 8


class TestHistoryEndpoints:
    def test_daily_summary_endpoint(self, client, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import time as dt_time

            today = datetime.now(tz).date()
            start = datetime.combine(today, dt_time.min, tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w, a = make_worker_with_assignment(db_session, None, name="Endpoint Worker Unique")

            _make_entry(db_session, w, a, Decimal("4.500"), utc_now + timedelta(hours=9))
            db_session.commit()

            response = client.get(f"/api/history/daily?date={today.isoformat()}&q=Endpoint+Worker+Unique")
            assert response.status_code == 200
            data = response.get_json()
            assert data["date"] == today.isoformat()
            assert data["summary"]["total_entries"] == 1
            assert data["summary"]["total_weight_kg"] == "4.500"
            assert len(data["workers"]) == 1

    def test_daily_summary_invalid_date_endpoint(self, client, db_session):
        response = client.get("/api/history/daily?date=2026-13-45")
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_daily_summary_empty_date_endpoint(self, client, db_session):
        response = client.get("/api/history/daily?date=2099-01-01")
        assert response.status_code == 200
        data = response.get_json()
        assert data["workers"] == []
        assert data["summary"]["total_entries"] == 0
        assert data["summary"]["total_weight_kg"] == "0.000"

    def test_worker_entries_endpoint(self, client, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import time as dt_time

            today = datetime.now(tz).date()
            start = datetime.combine(today, dt_time.min, tzinfo=tz)
            utc_now = start.astimezone(timezone.utc)

            w, a = make_worker_with_assignment(db_session, None, name="Entries Endpoint Unique")

            _make_entry(db_session, w, a, Decimal("2.500"), utc_now + timedelta(hours=10))
            db_session.commit()

            response = client.get(
                f"/api/history/assignments/{a.id}/entries?date={today.isoformat()}"
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["worker"]["assignment_id"] == a.id
            assert len(data["entries"]) == 1
            assert data["entries"][0]["weight_kg"] == "2.500"
            assert data["summary"]["entries_count"] == 1
            assert data["summary"]["total_weight_kg"] == "2.500"

    def test_worker_entries_nonexistent_worker_endpoint(self, client, db_session):
        response = client.get("/api/history/assignments/99999/entries?date=2026-08-31")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_worker_entries_no_entries_on_date(self, client, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import date

            w, a = make_worker_with_assignment(db_session, None, name="No Entries Endpoint Unique")

            response = client.get(
                f"/api/history/assignments/{a.id}/entries?date=2099-01-01"
            )
            assert response.status_code == 200
            data = response.get_json()
            assert data["entries"] == []
            assert data["summary"]["entries_count"] == 0
            assert data["summary"]["total_weight_kg"] == "0.000"

    def test_worker_entries_invalid_date_endpoint(self, client, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            w, a = make_worker_with_assignment(db_session, None, name="Invalid Date Endpoint Unique")

            response = client.get(
                f"/api/history/assignments/{a.id}/entries?date=not-a-date"
            )
            assert response.status_code == 400

    def test_worker_entries_time_in_timezone(self, client, db_session, app):
        tz = app.config["HARVEST_TIMEZONE"]
        with app.app_context():
            from datetime import time as dt_time

            today = datetime.now(tz).date()
            start = datetime.combine(today, dt_time.min, tzinfo=tz)
            utc_14 = start.astimezone(timezone.utc) + timedelta(hours=14)

            w, a = make_worker_with_assignment(db_session, None, name="TZ Endpoint Unique")

            _make_entry(db_session, w, a, Decimal("1.000"), utc_14)
            db_session.commit()

            response = client.get(
                f"/api/history/assignments/{a.id}/entries?date={today.isoformat()}"
            )
            data = response.get_json()
            assert data["entries"][0]["created_at"] == "14:00"


class TestHistoryPageOperationalToday:
    def test_history_page_operational_today(self, client, monkeypatch):
        monkeypatch.setattr("app.routes.views._operational_today", lambda: date(2026, 6, 17))
        response = client.get("/history")
        assert response.status_code == 200
        html = response.data.decode()
        assert 'HISTORY_CONFIG' in html
        assert 'operationalToday: "2026-06-17"' in html
