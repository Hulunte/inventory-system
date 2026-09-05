from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from flask import current_app
from sqlalchemy import func

from app.extensions import db
from app.models.harvest_entry import HarvestEntry
from app.models.worker import Worker


def _get_tz():
    return current_app.config["HARVEST_TIMEZONE"]


def _date_range_to_utc(operational_date, tz=None):
    if tz is None:
        tz = _get_tz()
    start_of_day = datetime.combine(operational_date, time.min, tzinfo=tz)
    end_of_day = start_of_day + timedelta(days=1)
    return start_of_day.astimezone(timezone.utc), end_of_day.astimezone(timezone.utc)


def _to_operational_timezone(dt_utc, tz=None):
    if tz is None:
        tz = _get_tz()
    return dt_utc.astimezone(tz)


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def get_daily_summary(operational_date, query_filter=None, tz=None):
    if tz is None:
        tz = _get_tz()
    start_utc, end_utc = _date_range_to_utc(operational_date, tz)

    q = (
        db.session.query(
            HarvestEntry.worker_id,
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
            HarvestEntry.worker_id,
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

        slot_num = r.worker_slot_number_snapshot
        slot_label = f"Trabajador {slot_num:03d}" if slot_num else None

        workers_data.append({
            "worker_id": r.worker_id,
            "worker_assignment_id": r.worker_assignment_id,
            "slot_number": slot_num,
            "slot_label": slot_label,
            "name": r.worker_name_snapshot,
            "barcode": r.worker_barcode_snapshot,
            "entries_count": r.entries_count,
            "total_weight_kg": str(worker_weight),
        })
        total_entries += r.entries_count
        total_weight += worker_weight

    return {
        "workers": workers_data,
        "summary": {
            "total_entries": total_entries,
            "total_weight_kg": str(total_weight),
        },
    }


def get_worker_entries(assignment_id, operational_date, tz=None):
    if tz is None:
        tz = _get_tz()
    start_utc, end_utc = _date_range_to_utc(operational_date, tz)

    entries = (
        HarvestEntry.query
        .filter(
            HarvestEntry.worker_assignment_id == assignment_id,
            HarvestEntry.created_at >= start_utc,
            HarvestEntry.created_at < end_utc,
            HarvestEntry.voided == False,
        )
        .order_by(HarvestEntry.created_at.asc())
        .all()
    )

    return entries
