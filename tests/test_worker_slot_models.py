"""Worker slot model and constraint tests.

These tests validate models, constraints, and pure logic helpers.
They do NOT run upgrade() or validate the real backfill.
Alembic migration validation requires a separate controlled test on
a backed-up database.
"""
import re

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.models.worker import Worker
from app.models.worker_assignment import WorkerAssignment
from app.models.harvest_entry import HarvestEntry


class TestWorkerNameNullable:
    def test_worker_name_nullable(self, db_session):
        w = Worker(barcode="TRB000050", name=None, slot_number=50)
        db_session.add(w)
        db_session.flush()
        assert w.name is None

    def test_worker_name_with_value(self, db_session):
        w = Worker(barcode="TRB000051", name="Juan Perez", slot_number=51)
        db_session.add(w)
        db_session.flush()
        assert w.name == "Juan Perez"


class TestSlotNumberPositive:
    def test_slot_zero_rejected(self, db_session):
        w = Worker(barcode="TRB000052", name="Zero", slot_number=0)
        db_session.add(w)
        with pytest.raises(Exception):
            db_session.flush()

    def test_slot_negative_rejected(self, db_session):
        w = Worker(barcode="TRB000053", name="Negative", slot_number=-1)
        db_session.add(w)
        with pytest.raises(Exception):
            db_session.flush()

    def test_slot_one_accepted(self, db_session):
        w = Worker(barcode="TRB000001", name="One", slot_number=1)
        db_session.add(w)
        db_session.flush()
        assert w.slot_number == 1

    def test_slot_151_rejected(self, db_session):
        w = Worker(barcode="TRB000151", name="Overflow", slot_number=151)
        db_session.add(w)
        with pytest.raises(Exception):
            db_session.flush()

    def test_slot_150_accepted(self, db_session):
        w = Worker(barcode="TRB000150", name="MaxSlot", slot_number=150)
        db_session.add(w)
        db_session.flush()
        assert w.slot_number == 150


class TestSlotNumberUnique:
    def test_duplicate_slot_rejected(self, db_session):
        w1 = Worker(barcode="TRB000054", name="First", slot_number=54)
        w2 = Worker(barcode="TRB000055", name="Second", slot_number=54)
        db_session.add_all([w1, w2])
        with pytest.raises(Exception):
            db_session.flush()


class TestSlotNumberRequired:
    def test_slot_none_rejected(self, db_session):
        w = Worker(barcode="TRB000056", name="NoSlot", slot_number=None)
        db_session.add(w)
        with pytest.raises(Exception):
            db_session.flush()


BARCODE_RE = re.compile(r"^TRB\d{6}$")


class TestBarcodeFormat:
    def test_valid_barcode_accepted(self, db_session):
        w = Worker(barcode="TRB000057", name="Valid", slot_number=57)
        db_session.add(w)
        db_session.flush()
        assert BARCODE_RE.match(w.barcode)

    def test_barcode_rejected_no_trb_prefix(self, db_session):
        w = Worker(barcode="12345", name="Bad", slot_number=58)
        db_session.add(w)
        with pytest.raises(Exception):
            db_session.flush()

    def test_barcode_rejected_too_short(self, db_session):
        w = Worker(barcode="TRB123", name="Short", slot_number=59)
        db_session.add(w)
        with pytest.raises(Exception):
            db_session.flush()

    def test_barcode_rejected_too_long(self, db_session):
        w = Worker(barcode="TRB0000001", name="Long", slot_number=60)
        db_session.add(w)
        with pytest.raises(Exception):
            db_session.flush()


class TestBarcodeMatchesSlot:
    def test_barcode_corresponds_to_slot(self, db_session):
        for slot in [1, 42, 100, 150]:
            expected = f"TRB{slot:06d}"
            w = Worker(barcode=expected, name=f"Slot{slot}", slot_number=slot)
            db_session.add(w)
        db_session.flush()

    def test_barcode_slot_mismatch_rejected(self, db_session):
        w = Worker(barcode="TRB000099", name="Mismatch", slot_number=61)
        db_session.add(w)
        with pytest.raises(Exception):
            db_session.flush()


class TestPartialUniqueOpenAssignment:
    def test_one_open_one_closed_ok(self, db_session):
        w = Worker(barcode="TRB000062", name="PU01", slot_number=62)
        db_session.add(w)
        db_session.flush()

        a1 = WorkerAssignment(
            worker_id=w.id, person_name="First",
            started_at=datetime.now(timezone.utc) - timedelta(hours=2),
            ended_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        a2 = WorkerAssignment(
            worker_id=w.id, person_name="Second",
            started_at=datetime.now(timezone.utc),
        )
        db_session.add_all([a1, a2])
        db_session.flush()

        assert a1.ended_at is not None
        assert a2.ended_at is None

    def test_two_open_same_worker_rejected(self, db_session):
        w = Worker(barcode="TRB000063", name="PU02", slot_number=63)
        db_session.add(w)
        db_session.flush()

        a1 = WorkerAssignment(
            worker_id=w.id, person_name="Open1",
            started_at=datetime.now(timezone.utc),
        )
        a2 = WorkerAssignment(
            worker_id=w.id, person_name="Open2",
            started_at=datetime.now(timezone.utc),
        )
        db_session.add_all([a1, a2])
        with pytest.raises(Exception):
            db_session.flush()


class TestPersonNameLength:
    def test_150_characters_accepted(self, db_session):
        name_150 = "A" * 150
        w = Worker(barcode="TRB000064", name="PN150", slot_number=64)
        db_session.add(w)
        db_session.flush()

        a = WorkerAssignment(worker_id=w.id, person_name=name_150)
        db_session.add(a)
        db_session.flush()
        assert len(a.person_name) == 150

    def test_151_characters_rejected(self, db_session):
        name_151 = "A" * 151
        w = Worker(barcode="TRB000065", name="PN151", slot_number=65)
        db_session.add(w)
        db_session.flush()

        a = WorkerAssignment(worker_id=w.id, person_name=name_151)
        db_session.add(a)
        with pytest.raises(Exception):
            db_session.flush()


class TestHistoricalBarcodePreserved:
    def test_snapshot_preserves_old_barcode(self, db_session):
        w = Worker(barcode="TRB000066", name="Historical", slot_number=66)
        db_session.add(w)
        db_session.flush()

        a = WorkerAssignment(
            worker_id=w.id, person_name="Historical",
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(a)
        db_session.flush()

        entry = HarvestEntry(
            worker_id=w.id,
            weight_kg=Decimal("5.000"),
            worker_assignment_id=a.id,
            worker_slot_number_snapshot=w.slot_number,
            worker_barcode_snapshot="12345",
            worker_name_snapshot="Historical",
        )
        db_session.add(entry)
        db_session.flush()

        assert entry.worker_barcode_snapshot == "12345"
        assert entry.worker_barcode_snapshot != w.barcode
        assert w.barcode == "TRB000066"


class TestStartedAtBeforeEntries:
    def test_assignment_started_at_before_all_entries(self, db_session):
        w = Worker(barcode="TRB000067", name="DateCheck", slot_number=67)
        db_session.add(w)
        db_session.flush()

        entry_time = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        assignment_time = datetime(2025, 6, 15, 9, 0, 0, tzinfo=timezone.utc)

        a = WorkerAssignment(
            worker_id=w.id, person_name="DateCheck",
            started_at=assignment_time,
        )
        db_session.add(a)
        db_session.flush()

        entry = HarvestEntry(
            worker_id=w.id,
            weight_kg=Decimal("3.000"),
            created_at=entry_time,
            worker_assignment_id=a.id,
            worker_slot_number_snapshot=w.slot_number,
            worker_barcode_snapshot=w.barcode,
            worker_name_snapshot="DateCheck",
        )
        db_session.add(entry)
        db_session.flush()

        assert a.started_at <= entry.created_at


class TestSnapshotAllOrNothing:
    def test_all_null_allowed(self, db_session):
        w = Worker(barcode="TRB000068", name="SnapNull", slot_number=68)
        db_session.add(w)
        db_session.flush()

        entry = HarvestEntry(
            worker_id=w.id,
            weight_kg=Decimal("2.000"),
        )
        db_session.add(entry)
        db_session.flush()
        assert entry.worker_assignment_id is None

    def test_all_populated_allowed(self, db_session):
        w = Worker(barcode="TRB000069", name="SnapFull", slot_number=69)
        db_session.add(w)
        db_session.flush()

        a = WorkerAssignment(worker_id=w.id, person_name="SnapFull")
        db_session.add(a)
        db_session.flush()

        entry = HarvestEntry(
            worker_id=w.id,
            weight_kg=Decimal("2.000"),
            worker_assignment_id=a.id,
            worker_slot_number_snapshot=w.slot_number,
            worker_barcode_snapshot=w.barcode,
            worker_name_snapshot="SnapFull",
        )
        db_session.add(entry)
        db_session.flush()
        assert entry.worker_assignment_id is not None

    def test_partial_assignment_id_only_rejected(self, db_session):
        w = Worker(barcode="TRB000070", name="SnapPart", slot_number=70)
        db_session.add(w)
        db_session.flush()

        a = WorkerAssignment(worker_id=w.id, person_name="SnapPart")
        db_session.add(a)
        db_session.flush()

        entry = HarvestEntry(
            worker_id=w.id,
            weight_kg=Decimal("2.000"),
            worker_assignment_id=a.id,
        )
        db_session.add(entry)
        with pytest.raises(Exception):
            db_session.flush()

    def test_partial_barcode_only_rejected(self, db_session):
        w = Worker(barcode="TRB000071", name="SnapPart2", slot_number=71)
        db_session.add(w)
        db_session.flush()

        entry = HarvestEntry(
            worker_id=w.id,
            weight_kg=Decimal("2.000"),
            worker_barcode_snapshot=w.barcode,
        )
        db_session.add(entry)
        with pytest.raises(Exception):
            db_session.flush()


class TestConstraintNames:
    def test_range_constraint_exists(self, db_session):
        from sqlalchemy import inspect
        inspector = inspect(db_session.get_bind())
        constraints = inspector.get_check_constraints("workers")
        names = [c["name"] for c in constraints]
        assert "ck_workers_slot_number_range" in names

    def test_old_positive_constraint_does_not_exist(self, db_session):
        from sqlalchemy import inspect
        inspector = inspect(db_session.get_bind())
        constraints = inspector.get_check_constraints("workers")
        names = [c["name"] for c in constraints]
        assert "ck_workers_slot_number_positive" not in names


class TestSlotSnapshotNeverNone:
    def test_linked_entry_slot_snapshot_is_integer(self, db_session):
        w = Worker(barcode="TRB000072", name="SnapInt", slot_number=72)
        db_session.add(w)
        db_session.flush()

        a = WorkerAssignment(worker_id=w.id, person_name="SnapInt")
        db_session.add(a)
        db_session.flush()

        entry = HarvestEntry(
            worker_id=w.id,
            weight_kg=Decimal("2.000"),
            worker_assignment_id=a.id,
            worker_slot_number_snapshot=w.slot_number,
            worker_barcode_snapshot=w.barcode,
            worker_name_snapshot="SnapInt",
        )
        db_session.add(entry)
        db_session.flush()

        assert entry.worker_slot_number_snapshot is not None
        assert isinstance(entry.worker_slot_number_snapshot, int)
        assert entry.worker_slot_number_snapshot == 72
