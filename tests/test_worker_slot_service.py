"""Worker slot service and helper tests.

These tests validate services, helpers, and pure logic.
They do NOT run upgrade() or validate the real backfill.
Alembic migration validation requires a separate controlled test on
a backed-up database.
"""
import re

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError as SAIntegrityError

from app.extensions import db
from app.models.worker import Worker
from app.models.worker_assignment import WorkerAssignment
from app.services.worker_slot_service import (
    assign_person,
    clean_all_assignments,
    validate_person_name,
    validate_barcode,
    search_worker_slots,
    get_open_assignment,
    BARCODE_PATTERN,
    MAX_SLOT_NUMBER,
)


class Test150BarcodesExact:
    def test_generates_exact_trb_001_to_150(self):
        expected = [f"TRB{i:06d}" for i in range(1, 151)]
        assert len(expected) == 150
        assert expected[0] == "TRB000001"
        assert expected[149] == "TRB000150"
        for code in expected:
            assert BARCODE_PATTERN.match(code), f"Invalid barcode: {code}"

    def test_all_150_are_unique(self):
        codes = [f"TRB{i:06d}" for i in range(1, 151)]
        assert len(set(codes)) == 150


class TestBarcodeCorrespondsToSlot:
    def test_each_barcode_matches_slot_number(self):
        for slot in range(1, 151):
            expected = f"TRB{slot:06d}"
            assert validate_barcode(expected), f"TRB{slot:06d} should be valid"

    def test_barcode_from_slot_number_formula(self):
        import re
        for slot in range(1, 151):
            barcode = "TRB" + str(slot).zfill(6)
            assert barcode == f"TRB{slot:06d}"
            m = re.match(r"^TRB(\d{6})$", barcode)
            assert m
            assert int(m.group(1)) == slot


class TestNewSlotsNoAssignment:
    def test_empty_slot_has_no_open_assignment(self, db_session):
        w = Worker(barcode="TRB000110", name=None, slot_number=110, active=True)
        db_session.add(w)
        db_session.flush()

        assignment = get_open_assignment(w.id)
        assert assignment is None

    def test_empty_slot_listed_in_search(self, db_session):
        w = Worker(barcode="TRB000111", name=None, slot_number=111, active=True)
        db_session.add(w)
        db_session.flush()

        results = search_worker_slots("TRB000111")
        assert len(results) == 1
        assert results[0].name is None


class TestAssignClosesPrevious:
    def test_reassign_closes_old_opens_new(self, db_session):
        w = Worker(barcode="TRB000112", name="Old", slot_number=112)
        db_session.add(w)
        db_session.flush()

        a1 = assign_person(w.id, "First Person")
        assert a1.ended_at is None

        a2 = assign_person(w.id, "Second Person")
        assert a1.ended_at is not None
        assert a2.ended_at is None
        assert a2.worker_id == w.id
        assert a2.person_name == "Second Person"

    def test_reassign_flush_before_new_assignment(self, db_session):
        w = Worker(barcode="TRB000113", name="FlushTest", slot_number=113)
        db_session.add(w)
        db_session.flush()

        a1 = assign_person(w.id, "First Person")
        assert a1.ended_at is None

        a2 = assign_person(w.id, "Second Person")

        open_count = db_session.query(WorkerAssignment).filter_by(
            worker_id=w.id, ended_at=None
        ).count()
        assert open_count == 1

        assert a1.ended_at is not None
        assert a2.ended_at is None
        assert a1.person_name == "First Person"
        assert a2.person_name == "Second Person"

    def test_assign_to_inactive_rejected(self, db_session):
        w = Worker(barcode="TRB000114", name="Inactive", slot_number=114, active=False)
        db_session.add(w)
        db_session.flush()

        with pytest.raises(ValueError, match="inactive"):
            assign_person(w.id, "Nobody")

    def test_assign_nonexistent_worker(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            assign_person(99999, "Ghost")


class TestRollbackOnIntegrityError:
    def test_session_clean_after_integrity_error(self, db_session):
        w = Worker(barcode="TRB000115", name="Rollback", slot_number=115)
        db_session.add(w)
        db_session.flush()

        a1 = assign_person(w.id, "First Person")
        assert a1.ended_at is None

        original_ended = a1.ended_at

        with patch(
            "app.services.worker_slot_service.db.session.commit",
            side_effect=SAIntegrityError("stmt", "params", Exception("test")),
        ):
            with pytest.raises(SAIntegrityError):
                assign_person(w.id, "Second Person")

        assert db_session.is_active

        db_session.refresh(a1)
        assert a1.ended_at == original_ended


class TestCleanAllAssignments:
    def test_clean_closes_all_and_nulls_names(self, db_session):
        w1 = Worker(barcode="TRB000116", name="Clean1", slot_number=116)
        w2 = Worker(barcode="TRB000117", name="Clean2", slot_number=117)
        db_session.add_all([w1, w2])
        db_session.flush()

        assign_person(w1.id, "Alice")
        assign_person(w2.id, "Bob")

        count = clean_all_assignments()
        assert count == 2

        a1 = get_open_assignment(w1.id)
        assert a1 is None
        a2 = get_open_assignment(w2.id)
        assert a2 is None

        db_session.refresh(w1)
        db_session.refresh(w2)
        assert w1.name is None
        assert w2.name is None


class TestValidateNameLimits:
    def test_max_150_accepted(self):
        name = "A" * 150
        result = validate_person_name(name)
        assert len(result) == 150

    def test_151_rejected(self):
        with pytest.raises(ValueError, match="at most 150"):
            validate_person_name("A" * 151)

    def test_empty_rejected(self):
        with pytest.raises(ValueError, match="required"):
            validate_person_name("")

    def test_whitespace_rejected(self):
        with pytest.raises(ValueError, match="required"):
            validate_person_name("   ")

    def test_non_string_rejected(self):
        with pytest.raises(ValueError, match="string"):
            validate_person_name(123)

    def test_strips_whitespace(self):
        result = validate_person_name("  Juan  ")
        assert result == "Juan"


class TestValidateBarcode:
    def test_valid_barcodes(self):
        assert validate_barcode("TRB000001")
        assert validate_barcode("TRB000150")
        assert validate_barcode("TRB999999")

    def test_invalid_barcodes(self):
        assert not validate_barcode("12345")
        assert not validate_barcode("TRB123")
        assert not validate_barcode("TRB0000001")
        assert not validate_barcode("TRB00000")
        assert not validate_barcode("trb000001")
        assert not validate_barcode("")
        assert not validate_barcode(None)
        assert not validate_barcode(123)


class TestMaxSlotConstant:
    def test_max_slot_is_150(self):
        assert MAX_SLOT_NUMBER == 150
