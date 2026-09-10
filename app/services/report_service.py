from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from flask import current_app
from sqlalchemy import case, func

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
            func.coalesce(func.sum(HarvestEntry.amount_mxn), 0).label("total_amount_mxn"),
            func.sum(case((HarvestEntry.registration_type == "scale", 1), else_=0)).label("scale_entries_count"),
            func.sum(case((HarvestEntry.registration_type == "sacks", 1), else_=0)).label("sack_entries_count"),
            func.coalesce(func.sum(case((HarvestEntry.registration_type == "sacks", HarvestEntry.sack_count), else_=0)), 0).label("total_sacks"),
            func.coalesce(func.sum(case((HarvestEntry.registration_type == "scale", HarvestEntry.weight_kg), else_=0)), 0).label("scale_weight_kg"),
            func.coalesce(func.sum(case((HarvestEntry.registration_type == "scale", HarvestEntry.amount_mxn), else_=0)), 0).label("scale_amount_mxn"),
            func.coalesce(func.sum(case((HarvestEntry.registration_type == "sacks", HarvestEntry.weight_kg), else_=0)), 0).label("sack_weight_kg"),
            func.coalesce(func.sum(case((HarvestEntry.registration_type == "sacks", HarvestEntry.amount_mxn), else_=0)), 0).label("sack_amount_mxn"),
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
    total_amount = Decimal("0.00")

    for r in rows:
        worker_weight = Decimal(str(r.total_weight_kg))
        worker_weight_formatted = _format_decimal(worker_weight)
        worker_amount = Decimal(str(r.total_amount_mxn))

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
                "total_amount_mxn": str(worker_amount.quantize(Decimal("0.01"))),
                "scale_entries_count": r.scale_entries_count,
                "sack_entries_count": r.sack_entries_count,
                "total_sacks": r.total_sacks,
                "scale_weight_kg": _format_decimal(r.scale_weight_kg),
                "scale_amount_mxn": str(Decimal(str(r.scale_amount_mxn)).quantize(Decimal("0.01"))),
                "sack_weight_kg": _format_decimal(r.sack_weight_kg),
                "sack_amount_mxn": str(Decimal(str(r.sack_amount_mxn)).quantize(Decimal("0.01"))),
            }
        )
        total_entries += r.entries_count
        total_weight += worker_weight
        total_amount += worker_amount

    scale_amount = sum((Decimal(w["scale_amount_mxn"]) for w in workers_data), Decimal("0"))
    sack_amount = sum((Decimal(w["sack_amount_mxn"]) for w in workers_data), Decimal("0"))
    scale_weight = sum((Decimal(w["scale_weight_kg"]) for w in workers_data), Decimal("0"))
    sack_weight = sum((Decimal(w["sack_weight_kg"]) for w in workers_data), Decimal("0"))
    return {
        "workers": workers_data,
        "summary": {
            "total_workers": len(workers_data),
            "total_entries": total_entries,
            "total_weight_kg": _format_decimal(total_weight),
            "total_amount_mxn": str(total_amount.quantize(Decimal("0.01"))),
            "scale": {"movements": sum(w["scale_entries_count"] for w in workers_data), "weight_kg": _format_decimal(scale_weight), "amount_mxn": str(scale_amount.quantize(Decimal("0.01")))},
            "sacks": {"movements": sum(w["sack_entries_count"] for w in workers_data), "sack_count": sum(w["total_sacks"] for w in workers_data), "weight_kg": _format_decimal(sack_weight), "amount_mxn": str(sack_amount.quantize(Decimal("0.01")))},
        },
    }
