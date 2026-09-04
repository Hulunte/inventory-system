import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from app.models.worker import Worker
from app.models.harvest_entry import HarvestEntry
from app.extensions import db
from app.services.harvest_service import get_daily_total, register_harvest
from app.services.history_service import get_daily_summary, get_worker_entries
from app.services.report_service import get_harvest_report
from zoneinfo import ZoneInfo


TZ = ZoneInfo("America/Chihuahua")


class TestVoidEntry:
    def test_void_correct(self, admin_client, db_session):
        worker = Worker(barcode="V001", name="Void Worker")
        db_session.add(worker)
        db_session.flush()

        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("10.000"), created_at=datetime.now(timezone.utc))
        db_session.add(entry)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/harvest-entries/{entry.id}/void",
            json={"reason": "Peso registrado incorrectamente"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["voided"] is True
        assert data["void_reason"] == "Peso registrado incorrectamente"
        assert data["voided_at"] is not None

    def test_void_empty_reason(self, admin_client, db_session):
        worker = Worker(barcode="V002", name="Empty Reason")
        db_session.add(worker)
        db_session.flush()

        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("5.000"), created_at=datetime.now(timezone.utc))
        db_session.add(entry)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/harvest-entries/{entry.id}/void",
            json={"reason": ""},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "reason is required"

    def test_void_whitespace_only_reason(self, admin_client, db_session):
        worker = Worker(barcode="V003", name="Whitespace Reason")
        db_session.add(worker)
        db_session.flush()

        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("5.000"), created_at=datetime.now(timezone.utc))
        db_session.add(entry)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/harvest-entries/{entry.id}/void",
            json={"reason": "   "},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 400

    def test_void_nonexistent_entry(self, admin_client, db_session):
        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            "/api/admin/harvest-entries/99999/void",
            json={"reason": "Nonexistent"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "Harvest entry not found"

    def test_void_already_voided(self, admin_client, db_session):
        worker = Worker(barcode="V004", name="Already Voided")
        db_session.add(worker)
        db_session.flush()

        entry = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("5.000"),
            created_at=datetime.now(timezone.utc),
            voided=True,
            voided_at=datetime.now(timezone.utc),
            void_reason="Already done",
        )
        db_session.add(entry)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        response = admin_client.patch(
            f"/api/admin/harvest-entries/{entry.id}/void",
            json={"reason": "Try again"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 409
        data = response.get_json()
        assert data["error"] == "Harvest entry is already voided"

    def test_void_preserves_worker_id(self, admin_client, db_session):
        worker = Worker(barcode="V005", name="Preserve Worker")
        db_session.add(worker)
        db_session.flush()

        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("7.500"), created_at=datetime.now(timezone.utc))
        db_session.add(entry)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        admin_client.patch(
            f"/api/admin/harvest-entries/{entry.id}/void",
            json={"reason": "Test preservation"},
            headers={"X-CSRF-Token": csrf},
        )

        updated = db_session.get(HarvestEntry, entry.id)
        assert updated.worker_id == worker.id

    def test_void_preserves_weight_kg(self, admin_client, db_session):
        worker = Worker(barcode="V006", name="Preserve Weight")
        db_session.add(worker)
        db_session.flush()

        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("12.345"), created_at=datetime.now(timezone.utc))
        db_session.add(entry)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        admin_client.patch(
            f"/api/admin/harvest-entries/{entry.id}/void",
            json={"reason": "Test weight preservation"},
            headers={"X-CSRF-Token": csrf},
        )

        updated = db_session.get(HarvestEntry, entry.id)
        assert updated.weight_kg == Decimal("12.345")

    def test_void_preserves_created_at(self, admin_client, db_session):
        worker = Worker(barcode="V007", name="Preserve Date")
        db_session.add(worker)
        db_session.flush()

        original_time = datetime(2026, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("3.000"), created_at=original_time)
        db_session.add(entry)
        db_session.commit()

        csrf = admin_client.get("/api/admin/session").get_json()["csrf_token"]
        admin_client.patch(
            f"/api/admin/harvest-entries/{entry.id}/void",
            json={"reason": "Test date preservation"},
            headers={"X-CSRF-Token": csrf},
        )

        updated = db_session.get(HarvestEntry, entry.id)
        assert updated.created_at == original_time


class TestVoidExcludesFromDailyTotal:
    def test_voided_excluded_from_daily_total(self, db_session):
        worker = Worker(barcode="VT001", name="Daily Total Void")
        db_session.add(worker)
        db_session.flush()

        e1 = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("10.000"), created_at=datetime.now(timezone.utc))
        e2 = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("5.000"),
            created_at=datetime.now(timezone.utc),
            voided=True,
            voided_at=datetime.now(timezone.utc),
            void_reason="test",
        )
        db_session.add_all([e1, e2])
        db_session.commit()

        total = get_daily_total(worker.id, tz=TZ)
        assert total == Decimal("10.000")


class TestVoidExcludesFromHistory:
    def test_voided_excluded_from_daily_summary(self, db_session):
        worker = Worker(barcode="VT002", name="History Void")
        db_session.add(worker)
        db_session.flush()

        today = datetime.now(TZ).date()

        e1 = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("8.000"), created_at=datetime.now(timezone.utc))
        e2 = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("4.000"),
            created_at=datetime.now(timezone.utc),
            voided=True,
            voided_at=datetime.now(timezone.utc),
            void_reason="test",
        )
        db_session.add_all([e1, e2])
        db_session.commit()

        result = get_daily_summary(today, query_filter="VT002", tz=TZ)
        assert len(result["workers"]) == 1
        assert result["workers"][0]["entries_count"] == 1
        assert result["workers"][0]["total_weight_kg"] == "8.000"

    def test_voided_excluded_from_worker_entries(self, db_session):
        worker = Worker(barcode="VT003", name="Worker Entries Void")
        db_session.add(worker)
        db_session.flush()

        today = datetime.now(TZ).date()

        e1 = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("6.000"), created_at=datetime.now(timezone.utc))
        e2 = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("3.000"),
            created_at=datetime.now(timezone.utc),
            voided=True,
            voided_at=datetime.now(timezone.utc),
            void_reason="test",
        )
        db_session.add_all([e1, e2])
        db_session.commit()

        entries = get_worker_entries(worker.id, today, TZ)
        assert len(entries) == 1
        assert entries[0].weight_kg == Decimal("6.000")


class TestVoidExcludesFromReports:
    def test_voided_excluded_from_report(self, db_session):
        worker = Worker(barcode="VT004", name="Report Void")
        db_session.add(worker)
        db_session.flush()

        today = datetime.now(TZ).date()

        e1 = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("15.000"), created_at=datetime.now(timezone.utc))
        e2 = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("7.000"),
            created_at=datetime.now(timezone.utc),
            voided=True,
            voided_at=datetime.now(timezone.utc),
            void_reason="test",
        )
        db_session.add_all([e1, e2])
        db_session.commit()

        result = get_harvest_report(today, today, query_filter="VT004", tz=TZ)
        assert len(result["workers"]) == 1
        assert result["workers"][0]["entries_count"] == 1
        assert result["summary"]["total_weight_kg"] == "15.000"


class TestAdminHarvestEntriesEndpoint:
    def test_list_entries(self, admin_client, db_session):
        worker = Worker(barcode="AEQ01", name="Admin Entries")
        db_session.add(worker)
        db_session.flush()

        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("5.000"), created_at=datetime.now(timezone.utc))
        db_session.add(entry)
        db_session.commit()

        response = admin_client.get("/api/admin/harvest-entries?q=AEQ01")
        assert response.status_code == 200
        data = response.get_json()
        entries = data["entries"]
        matching = [e for e in entries if e["worker"]["barcode"] == "AEQ01"]
        assert len(matching) >= 1
        assert matching[0]["weight_kg"] == "5.000"

    def test_list_entries_with_voided(self, admin_client, db_session):
        worker = Worker(barcode="AEQ02", name="Admin Entries Voided")
        db_session.add(worker)
        db_session.flush()

        e1 = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("5.000"), created_at=datetime.now(timezone.utc))
        e2 = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("3.000"),
            created_at=datetime.now(timezone.utc),
            voided=True,
            voided_at=datetime.now(timezone.utc),
            void_reason="test",
        )
        db_session.add_all([e1, e2])
        db_session.commit()

        response = admin_client.get("/api/admin/harvest-entries?q=AEQ02")
        assert response.status_code == 200
        data = response.get_json()
        entries = data["entries"]
        matching = [e for e in entries if e["worker"]["barcode"] == "AEQ02"]
        voided_entries = [e for e in matching if e["voided"]]
        active_entries = [e for e in matching if not e["voided"]]
        assert len(voided_entries) == 1
        assert len(active_entries) == 1


class TestVoidDefaultValues:
    def test_existing_entries_not_voided(self, db_session):
        worker = Worker(barcode="VD001", name="Default Void")
        db_session.add(worker)
        db_session.flush()

        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("5.000"), created_at=datetime.now(timezone.utc))
        db_session.add(entry)
        db_session.commit()

        fetched = db_session.get(HarvestEntry, entry.id)
        assert fetched.voided is False
        assert fetched.voided_at is None
        assert fetched.void_reason is None

    def test_new_entry_defaults_not_voided(self, db_session):
        from app.models.product import Product
        worker = Worker(barcode="VD002", name="New Default")
        db_session.add(worker)
        product = Product(name="VoidProd", rate_per_kg=Decimal("2.00"))
        db_session.add(product)
        db_session.commit()

        entry, _ = register_harvest("VD002", Decimal("3.000"), product.id)
        assert entry.voided is False
        assert entry.voided_at is None
        assert entry.void_reason is None


class TestCheckConstraint:
    def _make_worker(self, db_session, barcode="CK001"):
        worker = Worker(barcode=barcode, name="CK Worker")
        db_session.add(worker)
        db_session.flush()
        return worker

    def test_not_voided_all_null(self, db_session):
        worker = self._make_worker(db_session, "CK001")
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("1.000"),
                             created_at=datetime.now(timezone.utc),
                             voided=False, voided_at=None, void_reason=None)
        db_session.add(entry)
        db_session.commit()

    def test_voided_with_valid_reason_and_timestamp(self, db_session):
        worker = self._make_worker(db_session, "CK002")
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("1.000"),
                             created_at=datetime.now(timezone.utc),
                             voided=True, voided_at=datetime.now(timezone.utc),
                             void_reason="Peso incorrecto")
        db_session.add(entry)
        db_session.commit()

    def test_reject_not_voided_with_voided_at(self, db_session):
        worker = self._make_worker(db_session, "CK003")
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("1.000"),
                             created_at=datetime.now(timezone.utc),
                             voided=False, voided_at=datetime.now(timezone.utc),
                             void_reason=None)
        db_session.add(entry)
        with pytest.raises(Exception):
            db_session.commit()

    def test_reject_not_voided_with_void_reason(self, db_session):
        worker = self._make_worker(db_session, "CK004")
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("1.000"),
                             created_at=datetime.now(timezone.utc),
                             voided=False, voided_at=None,
                             void_reason="Some reason")
        db_session.add(entry)
        with pytest.raises(Exception):
            db_session.commit()

    def test_reject_voided_with_null_voided_at(self, db_session):
        worker = self._make_worker(db_session, "CK005")
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("1.000"),
                             created_at=datetime.now(timezone.utc),
                             voided=True, voided_at=None,
                             void_reason="reason")
        db_session.add(entry)
        with pytest.raises(Exception):
            db_session.commit()

    def test_reject_voided_with_null_void_reason(self, db_session):
        worker = self._make_worker(db_session, "CK006")
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("1.000"),
                             created_at=datetime.now(timezone.utc),
                             voided=True, voided_at=datetime.now(timezone.utc),
                             void_reason=None)
        db_session.add(entry)
        with pytest.raises(Exception):
            db_session.commit()

    def test_reject_voided_with_empty_reason(self, db_session):
        worker = self._make_worker(db_session, "CK007")
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("1.000"),
                             created_at=datetime.now(timezone.utc),
                             voided=True, voided_at=datetime.now(timezone.utc),
                             void_reason="")
        db_session.add(entry)
        with pytest.raises(Exception):
            db_session.commit()

    def test_reject_voided_with_whitespace_only_reason(self, db_session):
        worker = self._make_worker(db_session, "CK008")
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("1.000"),
                             created_at=datetime.now(timezone.utc),
                             voided=True, voided_at=datetime.now(timezone.utc),
                             void_reason="   ")
        db_session.add(entry)
        with pytest.raises(Exception):
            db_session.commit()


class TestVoidedAtLocal:
    """Tests for the voided_at_local field in admin listing responses."""

    def test_non_voided_entry_has_voided_at_local_none(self, admin_client, db_session):
        worker = Worker(barcode="VAL02", name="Active Local")
        db_session.add(worker)
        db_session.flush()

        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("3.000"),
                             created_at=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc))
        db_session.add(entry)
        db_session.commit()

        response = admin_client.get(f"/api/admin/harvest-entries?q=VAL02&date=2026-06-15")
        data = response.get_json()
        entries = data["entries"]
        active = [e for e in entries if not e["voided"]]
        assert len(active) == 1
        assert active[0]["voided_at_local"] is None
        assert active[0]["voided_at"] is None

    def test_voided_at_local_cross_day_boundary(self, admin_client, db_session):
        """05:59:59 UTC on Jun 16 = 23:59:59 Chihuahua on Jun 15."""
        worker = Worker(barcode="VAL04", name="Cross Day")
        db_session.add(worker)
        db_session.flush()

        voided_utc = datetime(2026, 6, 16, 5, 59, 59, tzinfo=timezone.utc)
        entry = HarvestEntry(worker_id=worker.id, weight_kg=Decimal("1.000"),
                             created_at=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
                             voided=True, voided_at=voided_utc,
                             void_reason="Cross day test")
        db_session.add(entry)
        db_session.commit()

        response = admin_client.get(f"/api/admin/harvest-entries?q=VAL04&date=2026-06-15")
        data = response.get_json()
        entries = data["entries"]
        matching = [e for e in entries if e["worker"]["barcode"] == "VAL04"]
        assert len(matching) == 1
        assert matching[0]["voided_at_local"] == "15/06/2026 23:59:59"
        assert matching[0]["voided_at"] is not None
