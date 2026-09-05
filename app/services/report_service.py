from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from flask import current_app
from sqlalchemy import func

from app.extensions import db
from app.models.harvest_entry import HarvestEntry
from app.models.worker import Worker


def _get_tz():
    return current_app.config["HARVEST_TIMEZONE"]


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _format_decimal(value):
    d = Decimal(str(value))
    return str(d.quantize(Decimal("0.001")))


def date_range_to_utc(start_date, end_date, tz=None):
    if tz is None:
        tz = _get_tz()
    start_utc = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(timezone.utc)
    end_utc = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    return start_utc, end_utc


def get_week_ranges(reference_date):
    monday_current = reference_date - timedelta(days=reference_date.weekday())
    sunday_current = monday_current + timedelta(days=6)

    monday_previous = monday_current - timedelta(days=7)
    sunday_previous = monday_previous + timedelta(days=6)

    return (monday_current, sunday_current), (monday_previous, sunday_previous)


def get_harvest_report(start_date, end_date, query_filter=None, tz=None):
    if tz is None:
        tz = _get_tz()

    start_utc, end_utc = date_range_to_utc(start_date, end_date, tz)

    q = (
        db.session.query(
            HarvestEntry.worker_assignment_id,
            HarvestEntry.worker_slot_number_snapshot,
            HarvestEntry.worker_name_snapshot,
            HarvestEntry.worker_barcode_snapshot,
            func.count(HarvestEntry.id).label("entries_count"),
            func.coalesce(func.sum(HarvestEntry.weight_kg), 0).label("total_weight_kg"),
        )
        .filter(
            HarvestEntry.created_at >= start_utc,
            HarvestEntry.created_at < end_utc,
            HarvestEntry.voided == False,
        )
        .group_by(
            HarvestEntry.worker_assignment_id,
            HarvestEntry.worker_slot_number_snapshot,
            HarvestEntry.worker_name_snapshot,
            HarvestEntry.worker_barcode_snapshot,
        )
        .order_by(HarvestEntry.worker_slot_number_snapshot.asc().nullslast())
    )

    if query_filter:
        pattern = f"%{query_filter}%"
        q = q.filter(
            db.or_(
                HarvestEntry.worker_name_snapshot.ilike(pattern),
                HarvestEntry.worker_barcode_snapshot.ilike(pattern),
            )
        )

    rows = q.all()

    workers_data = []
    total_entries = 0
    total_weight = Decimal("0.000")

    for r in rows:
        worker_weight = Decimal(str(r.total_weight_kg))
        worker_weight_formatted = _format_decimal(worker_weight)

        slot_num = r.worker_slot_number_snapshot
        slot_label = f"Trabajador {slot_num:03d}" if slot_num else None

        workers_data.append(
            {
                "worker_assignment_id": r.worker_assignment_id,
                "slot_number": slot_num,
                "slot_label": slot_label,
                "name": r.worker_name_snapshot,
                "barcode": r.worker_barcode_snapshot,
                "entries_count": r.entries_count,
                "total_weight_kg": worker_weight_formatted,
            }
        )
        total_entries += r.entries_count
        total_weight += worker_weight

    return {
        "workers": workers_data,
        "summary": {
            "total_workers": len(workers_data),
            "total_entries": total_entries,
            "total_weight_kg": _format_decimal(total_weight),
        },
    }
