"""Tests for ticket_service.py daily calculation logic."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models.harvest_entry import HarvestEntry
from app.models.product import Product
from app.models.worker import Worker
from app.models.worker_assignment import WorkerAssignment
from app.services.ticket_service import (
    get_daily_tickets,
    get_single_ticket,
    serialize_daily_response,
    serialize_ticket,
)
from tests.conftest import make_worker, make_assignment, make_worker_with_assignment

TZ = ZoneInfo("America/Chihuahua")


def _ensure_product(db_session, name="Naranja", rate="12.50"):
    product = Product.query.filter_by(name=name).first()
    if product is None:
        product = Product(name=name, rate_per_kg=Decimal(rate), active=True)
        db_session.add(product)
        db_session.flush()
    return product


def _make_entry(db_session, worker, assignment, weight_kg, created_at,
                product=None, product_name=None, rate_per_kg=None, amount_mxn=None):
    if product:
        product_name = product.name
        rate_per_kg = Decimal(str(product.rate_per_kg))
        amount_mxn = Decimal(str(weight_kg)) * rate_per_kg
    entry = HarvestEntry(
        worker_id=worker.id,
        weight_kg=Decimal(str(weight_kg)),
        product_id=product.id if product else None,
        product_name_snapshot=product_name,
        rate_per_kg_snapshot=rate_per_kg,
        amount_mxn=amount_mxn,
        created_at=created_at,
        worker_assignment_id=assignment.id,
        worker_slot_number_snapshot=worker.slot_number,
        worker_barcode_snapshot=worker.barcode,
        worker_name_snapshot=assignment.person_name,
    )
    db_session.add(entry)
    db_session.flush()
    return entry


class TestDailyTicketsOneProduct:
    def test_one_assignment_one_product(self, db_session):
        worker, assignment = make_worker_with_assignment(
            db_session, slot_number=10, person_name="Juan Perez"
        )
        product = _ensure_product(db_session, "Naranja", "12.50")

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 50.0, created, product=product)

        result = get_daily_tickets(op_date, tz=TZ)
        assert len(result["tickets"]) == 1
        t = result["tickets"][0]
        assert t.worker_name == "Juan Perez"
        assert t.slot_number == 10
        assert t.total_weight_kg == Decimal("50.000")
        assert t.total_amount_mxn == Decimal("625.00")
        assert len(t.product_lines) == 1
        assert t.product_lines[0].product_name == "Naranja"
        assert t.has_incomplete_amounts is False


class TestDailyTicketsMultipleProducts:
    def test_one_assignment_three_products(self, db_session):
        worker, assignment = make_worker_with_assignment(
            db_session, slot_number=20, person_name="Maria Lopez"
        )
        p1 = _ensure_product(db_session, "Naranja", "12.50")
        p2 = _ensure_product(db_session, "Limon", "15.00")
        p3 = _ensure_product(db_session, "Mandarina", "10.00")

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 30.0, created, product=p1)
        _make_entry(db_session, worker, assignment, 20.0, created, product=p2)
        _make_entry(db_session, worker, assignment, 10.0, created, product=p3)

        result = get_daily_tickets(op_date, tz=TZ)
        t = result["tickets"][0]
        assert len(t.product_lines) == 3
        assert t.total_weight_kg == Decimal("60.000")
        expected_amount = Decimal("30") * Decimal("12.50") + Decimal("20") * Decimal("15.00") + Decimal("10") * Decimal("10.00")
        assert t.total_amount_mxn == expected_amount


class TestDailyTicketsGrouping:
    def test_same_product_same_price_grouped(self, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=30)
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 25.0, created, product=product)
        _make_entry(db_session, worker, assignment, 35.0, created, product=product)

        result = get_daily_tickets(op_date, tz=TZ)
        t = result["tickets"][0]
        assert len(t.product_lines) == 1
        assert t.total_weight_kg == Decimal("60.000")

    def test_same_product_different_prices_separated(self, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=31)
        product = _ensure_product(db_session, "Naranja", "12.50")

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 25.0, created, product=product)

        entry2 = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("35.000"),
            product_id=product.id,
            product_name_snapshot="Naranja",
            rate_per_kg_snapshot=Decimal("15.00"),
            amount_mxn=Decimal("525.00"),
            created_at=created,
            worker_assignment_id=assignment.id,
            worker_slot_number_snapshot=worker.slot_number,
            worker_barcode_snapshot=worker.barcode,
            worker_name_snapshot=assignment.person_name,
        )
        db_session.add(entry2)
        db_session.flush()

        result = get_daily_tickets(op_date, tz=TZ)
        t = result["tickets"][0]
        assert len(t.product_lines) == 2
        rates = [line.rate_per_kg for line in t.product_lines]
        assert Decimal("12.50") in rates
        assert Decimal("15.00") in rates


class TestDailyTicketsVoidedExcluded:
    def test_voided_entries_excluded(self, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=40)
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 50.0, created, product=product)
        entry2 = _make_entry(db_session, worker, assignment, 30.0, created, product=product)
        entry2.voided = True
        entry2.voided_at = created
        entry2.void_reason = "Error"
        db_session.flush()

        result = get_daily_tickets(op_date, tz=TZ)
        t = result["tickets"][0]
        assert t.total_weight_kg == Decimal("50.000")


class TestDailyTicketsTwoAssignmentsSameSlot:
    def test_two_people_same_slot(self, db_session):
        from tests.conftest import make_worker, make_assignment
        worker = make_worker(db_session, slot_number=50)

        a1 = make_assignment(db_session, worker, "Persona A")
        db_session.flush()
        a1.ended_at = a1.started_at + timedelta(seconds=1)
        db_session.flush()

        a2 = make_assignment(db_session, worker, "Persona B")
        db_session.flush()

        product = _ensure_product(db_session)
        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, a1, 20.0, created, product=product)
        _make_entry(db_session, worker, a2, 30.0, created, product=product)

        result = get_daily_tickets(op_date, tz=TZ)
        assert len(result["tickets"]) == 2
        names = {t.worker_name for t in result["tickets"]}
        assert "Persona A" in names
        assert "Persona B" in names


class TestDailyTicketsSnapshotsPreserved:
    def test_snapshots_used_not_current(self, db_session):
        worker, assignment = make_worker_with_assignment(
            db_session, slot_number=60, person_name="Original Name"
        )
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 25.0, created, product=product)

        assignment.person_name = "Changed Name"
        db_session.flush()

        result = get_daily_tickets(op_date, tz=TZ)
        t = result["tickets"][0]
        assert t.worker_name == "Original Name"


class TestDailyTicketsOrdering:
    def test_ordered_by_slot_then_assignment(self, db_session):
        w1, a1 = make_worker_with_assignment(db_session, slot_number=30, person_name="Zulu")
        w2, a2 = make_worker_with_assignment(db_session, slot_number=10, person_name="Alpha")
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, w2, a2, 10.0, created, product=product)
        _make_entry(db_session, w1, a1, 20.0, created, product=product)

        result = get_daily_tickets(op_date, tz=TZ)
        assert result["tickets"][0].slot_number == 10
        assert result["tickets"][1].slot_number == 30


class TestDailyTicketsTimezone:
    def test_operational_date_boundaries(self, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=70)
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

        entry = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("40.000"),
            product_id=product.id,
            product_name_snapshot=product.name,
            rate_per_kg_snapshot=Decimal(str(product.rate_per_kg)),
            amount_mxn=Decimal("40") * Decimal(str(product.rate_per_kg)),
            created_at=created,
            worker_assignment_id=assignment.id,
            worker_slot_number_snapshot=worker.slot_number,
            worker_barcode_snapshot=worker.barcode,
            worker_name_snapshot=assignment.person_name,
        )
        db_session.add(entry)
        db_session.flush()

        result = get_daily_tickets(op_date, tz=TZ)
        t = result["tickets"][0]
        assert t.total_weight_kg == Decimal("40.000")


class TestDailyTicketsEmptyDay:
    def test_no_movements_returns_empty(self, db_session):
        op_date = date(2020, 1, 1)
        result = get_daily_tickets(op_date, tz=TZ)
        assert result["tickets"] == []
        assert result["total_workers"] == 0
        assert result["total_day_weight_kg"] == Decimal("0.000")
        assert result["total_day_amount_mxn"] == Decimal("0.000")


class TestDailyTicketsLegacyMovements:
    def test_legacy_no_product_no_amount(self, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=80)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        entry = HarvestEntry(
            worker_id=worker.id,
            weight_kg=Decimal("15.000"),
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

        result = get_daily_tickets(op_date, tz=TZ)
        t = result["tickets"][0]
        assert t.has_incomplete_amounts is True
        assert t.total_weight_kg == Decimal("15.000")
        assert t.total_amount_mxn == Decimal("0.000")
        assert len(t.product_lines) == 1
        assert "Sin producto" in t.product_lines[0].product_name
        assert t.product_lines[0].amount_mxn is None

    def test_mixed_legacy_and_modern(self, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=81)
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        entry_legacy = HarvestEntry(
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
        db_session.add(entry_legacy)
        db_session.flush()
        _make_entry(db_session, worker, assignment, 20.0, created, product=product)

        result = get_daily_tickets(op_date, tz=TZ)
        t = result["tickets"][0]
        assert t.has_incomplete_amounts is True
        assert t.total_weight_kg == Decimal("30.000")
        assert t.total_amount_mxn == Decimal("250.00")


class TestDailyTicketsFilter:
    def test_filter_by_name(self, db_session):
        w1, a1 = make_worker_with_assignment(db_session, slot_number=90, person_name="Juan")
        w2, a2 = make_worker_with_assignment(db_session, slot_number=91, person_name="Maria")
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, w1, a1, 10.0, created, product=product)
        _make_entry(db_session, w2, a2, 20.0, created, product=product)

        result = get_daily_tickets(op_date, query_filter="Juan", tz=TZ)
        assert len(result["tickets"]) == 1
        assert result["tickets"][0].worker_name == "Juan"

    def test_filter_by_barcode(self, db_session):
        w1, a1 = make_worker_with_assignment(db_session, slot_number=92)
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, w1, a1, 10.0, created, product=product)

        barcode = w1.barcode
        result = get_daily_tickets(op_date, query_filter=barcode, tz=TZ)
        assert len(result["tickets"]) == 1

    def test_filter_by_slot_number(self, db_session):
        w1, a1 = make_worker_with_assignment(db_session, slot_number=93)
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, w1, a1, 10.0, created, product=product)

        result = get_daily_tickets(op_date, query_filter="93", tz=TZ)
        assert len(result["tickets"]) == 1


class TestDailyTicketsTotals:
    def test_day_totals(self, db_session):
        w1, a1 = make_worker_with_assignment(db_session, slot_number=100)
        w2, a2 = make_worker_with_assignment(db_session, slot_number=101)
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, w1, a1, 10.0, created, product=product)
        _make_entry(db_session, w2, a2, 20.0, created, product=product)

        result = get_daily_tickets(op_date, tz=TZ)
        assert result["total_workers"] == 2
        assert result["total_day_weight_kg"] == Decimal("30.000")
        expected_amount = Decimal("10") * Decimal("12.50") + Decimal("20") * Decimal("12.50")
        assert result["total_day_amount_mxn"] == expected_amount


class TestSerializeTicket:
    def test_serialization(self, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=110)
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 50.0, created, product=product)

        result = get_daily_tickets(op_date, tz=TZ)
        serialized = serialize_ticket(result["tickets"][0])
        assert serialized["slot_number"] == 110
        assert serialized["total_weight_kg"] == "50.000"
        assert serialized["total_amount_mxn"] == "625.00"
        assert serialized["has_incomplete_amounts"] is False
        assert serialized["product_lines"][0]["amount_mxn"] == "625.00"

    def test_serialize_legacy_amount_is_none(self, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=112)

        op_date = date(2026, 6, 15)
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

        result = get_daily_tickets(op_date, tz=TZ)
        serialized = serialize_ticket(result["tickets"][0])
        assert serialized["product_lines"][0]["amount_mxn"] is None
        assert serialized["has_incomplete_amounts"] is True

    def test_serialize_daily_response(self, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=111)
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 50.0, created, product=product)

        result = get_daily_tickets(op_date, tz=TZ)
        serialized = serialize_daily_response(result)
        assert "tickets" in serialized
        assert serialized["total_workers"] == 1
        assert "total_day_weight_kg" in serialized
        assert "total_day_amount_mxn" in serialized


class TestGetSingleTicket:
    def test_existing_assignment(self, db_session):
        worker, assignment = make_worker_with_assignment(db_session, slot_number=120)
        product = _ensure_product(db_session)

        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 50.0, created, product=product)

        ticket = get_single_ticket(op_date, assignment.id, tz=TZ)
        assert ticket is not None
        assert ticket.worker_assignment_id == assignment.id

    def test_nonexistent_assignment(self, db_session):
        op_date = date(2026, 6, 15)
        ticket = get_single_ticket(op_date, 99999, tz=TZ)
        assert ticket is None


class TestQueryCount:
    def test_get_daily_tickets_single_query(self, db_session):
        """Verify get_daily_tickets uses a single query, not N+1, for up to 150 tickets."""
        product = _ensure_product(db_session)
        op_date = date(2026, 6, 15)
        created = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)

        workers = []
        for i in range(1, 51):
            w, a = make_worker_with_assignment(db_session, slot_number=i)
            _make_entry(db_session, w, a, float(i), created, product=product)
            workers.append((w, a))
        db_session.flush()

        from sqlalchemy import event

        query_count = [0]

        @event.listens_for(db_session.get_bind(), "before_cursor_execute")
        def count_queries(conn, cursor, statement, parameters, context, executemany):
            query_count[0] += 1

        initial_count = query_count[0]
        result = get_daily_tickets(op_date, tz=TZ)
        final_count = query_count[0]

        queries_executed = final_count - initial_count
        assert queries_executed <= 1, f"Expected 1 query, got {queries_executed}"
        assert len(result["tickets"]) == 50


class TestClosedAssignmentHistoricalVisibility:
    """Regression: closed assignment movements must appear in their operational date."""

    def test_closed_assignment_with_movements_appears(self, db_session):
        worker, assignment = make_worker_with_assignment(
            db_session, slot_number=1, person_name="Historical Worker"
        )
        assignment.ended_at = assignment.started_at + timedelta(hours=8)
        db_session.flush()

        product = _ensure_product(db_session, "Naranja", "12.50")
        op_date = date(2026, 8, 31)
        created = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 50.0, created, product=product)
        db_session.flush()

        result = get_daily_tickets(op_date, tz=TZ)
        assert len(result["tickets"]) == 1
        t = result["tickets"][0]
        assert t.worker_assignment_id == assignment.id
        assert t.worker_name == "Historical Worker"
        assert t.total_weight_kg == Decimal("50.000")

    def test_later_open_assignment_does_not_hide_historical(self, db_session):
        worker, closed_assignment = make_worker_with_assignment(
            db_session, slot_number=2, person_name="Old Worker"
        )
        closed_assignment.ended_at = closed_assignment.started_at + timedelta(hours=8)
        db_session.flush()

        product = _ensure_product(db_session, "Naranja", "12.50")
        op_date = date(2026, 8, 31)
        created = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, closed_assignment, 30.0, created, product=product)
        db_session.flush()

        open_assignment = make_assignment(db_session, worker, "New Worker")
        db_session.flush()

        result = get_daily_tickets(op_date, tz=TZ)
        assert len(result["tickets"]) == 1
        t = result["tickets"][0]
        assert t.worker_assignment_id == closed_assignment.id
        assert t.worker_name == "Old Worker"

    def test_two_assignments_same_slot_different_dates(self, db_session):
        worker, a1 = make_worker_with_assignment(
            db_session, slot_number=3, person_name="Day1 Worker"
        )
        a1.ended_at = a1.started_at + timedelta(hours=8)
        db_session.flush()

        product = _ensure_product(db_session, "Naranja", "12.50")

        _make_entry(db_session, worker, a1, 20.0,
                     datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc), product=product)
        db_session.flush()

        a2 = make_assignment(db_session, worker, "Day2 Worker")
        db_session.flush()
        a2.ended_at = a2.started_at + timedelta(hours=8)
        db_session.flush()

        _make_entry(db_session, worker, a2, 40.0,
                     datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc), product=product)
        db_session.flush()

        result_aug = get_daily_tickets(date(2026, 8, 31), tz=TZ)
        assert len(result_aug["tickets"]) == 1
        assert result_aug["tickets"][0].worker_name == "Day1 Worker"

        result_sep = get_daily_tickets(date(2026, 9, 1), tz=TZ)
        assert len(result_sep["tickets"]) == 1
        assert result_sep["tickets"][0].worker_name == "Day2 Worker"

    def test_search_by_historical_barcode(self, db_session):
        worker, assignment = make_worker_with_assignment(
            db_session, slot_number=4, person_name="Barcode Worker"
        )
        assignment.ended_at = assignment.started_at + timedelta(hours=8)
        db_session.flush()

        product = _ensure_product(db_session, "Naranja", "12.50")
        op_date = date(2026, 8, 31)
        created = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 25.0, created, product=product)
        db_session.flush()

        barcode = worker.barcode
        result = get_daily_tickets(op_date, query_filter=barcode, tz=TZ)
        assert len(result["tickets"]) == 1
        assert result["tickets"][0].worker_barcode == barcode

    def test_voided_entries_still_excluded(self, db_session):
        worker, assignment = make_worker_with_assignment(
            db_session, slot_number=5, person_name="Void Worker"
        )
        assignment.ended_at = assignment.started_at + timedelta(hours=8)
        db_session.flush()

        product = _ensure_product(db_session, "Naranja", "12.50")
        op_date = date(2026, 8, 31)
        created = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)
        entry = _make_entry(db_session, worker, assignment, 50.0, created, product=product)
        entry.voided = True
        entry.voided_at = created
        entry.void_reason = "Error"
        db_session.flush()

        result = get_daily_tickets(op_date, tz=TZ)
        assert len(result["tickets"]) == 0

    def test_date_uses_harvest_timezone(self, db_session):
        worker, assignment = make_worker_with_assignment(
            db_session, slot_number=6, person_name="TZ Worker"
        )
        assignment.ended_at = assignment.started_at + timedelta(hours=8)
        db_session.flush()

        product = _ensure_product(db_session, "Naranja", "12.50")

        entry_aug31_utc = datetime(2026, 8, 31, 12, 0, 0, tzinfo=timezone.utc)
        _make_entry(db_session, worker, assignment, 10.0, entry_aug31_utc, product=product)
        db_session.flush()

        result_aug31 = get_daily_tickets(date(2026, 8, 31), tz=TZ)
        assert len(result_aug31["tickets"]) == 1

        result_aug30 = get_daily_tickets(date(2026, 8, 30), tz=TZ)
        assert len(result_aug30["tickets"]) == 0

        result_sep1 = get_daily_tickets(date(2026, 9, 1), tz=TZ)
        assert len(result_sep1["tickets"]) == 0

    def test_empty_date_truly_empty(self, db_session):
        result = get_daily_tickets(date(2019, 12, 25), tz=TZ)
        assert result["tickets"] == []

    def test_endpoint_returns_historical_ticket(self, admin_client, db_session):
        from tests.conftest import make_worker_with_assignment
        worker, assignment = make_worker_with_assignment(
            db_session, slot_number=7, person_name="API Worker"
        )
        assignment.ended_at = assignment.started_at + timedelta(hours=8)
        db_session.flush()

        product = _ensure_product(db_session, "Naranja", "12.50")
        _make_entry(db_session, worker, assignment, 35.0,
                     datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc), product=product)
        db_session.commit()

        resp = admin_client.get("/api/tickets/daily?date=2026-08-31")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tickets"]) == 1
        assert data["tickets"][0]["worker_name"] == "API Worker"
        assert data["tickets"][0]["total_weight_kg"] == "35.000"

    def test_endpoint_does_not_depend_on_current_worker_name(self, admin_client, db_session):
        from tests.conftest import make_worker_with_assignment
        worker, assignment = make_worker_with_assignment(
            db_session, slot_number=8, person_name="Original Name"
        )
        assignment.ended_at = assignment.started_at + timedelta(hours=8)
        db_session.flush()

        product = _ensure_product(db_session, "Naranja", "12.50")
        _make_entry(db_session, worker, assignment, 20.0,
                     datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc), product=product)
        db_session.flush()

        assignment.person_name = "Changed Name"
        db_session.commit()

        resp = admin_client.get("/api/tickets/daily?date=2026-08-31")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["tickets"]) == 1
        assert data["tickets"][0]["worker_name"] == "Original Name"

    def test_closed_assignment_not_filtered_by_ended_at(self, db_session):
        worker, assignment = make_worker_with_assignment(
            db_session, slot_number=9, person_name="Closed Worker"
        )
        assignment.ended_at = assignment.started_at + timedelta(hours=1)
        db_session.flush()

        product = _ensure_product(db_session, "Naranja", "12.50")
        _make_entry(db_session, worker, assignment, 15.0,
                     datetime(2026, 8, 31, 14, 0, 0, tzinfo=timezone.utc), product=product)
        db_session.flush()

        result = get_daily_tickets(date(2026, 8, 31), tz=TZ)
        assert len(result["tickets"]) == 1
        assert result["tickets"][0].worker_assignment_id == assignment.id
