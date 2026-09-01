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


def get_harvest_report(start_date, end_date, query_filter=None, tz=None):
    if tz is None:
        tz = _get_tz()

    start_utc = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(timezone.utc)
    end_of_end_day = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
    end_utc = end_of_end_day.astimezone(timezone.utc)

    q = (
        db.session.query(
            Worker.id,
            Worker.name,
            Worker.barcode,
            func.count(HarvestEntry.id).label("entries_count"),
            func.coalesce(func.sum(HarvestEntry.weight_kg), 0).label("total_weight_kg"),
        )
        .join(HarvestEntry, Worker.id == HarvestEntry.worker_id)
        .filter(
            HarvestEntry.created_at >= start_utc,
            HarvestEntry.created_at < end_utc,
        )
        .group_by(Worker.id, Worker.name, Worker.barcode)
        .order_by(Worker.name.asc())
    )

    if query_filter:
        pattern = f"%{query_filter}%"
        q = q.filter(
            db.or_(
                Worker.name.ilike(pattern),
                Worker.barcode.ilike(pattern),
            )
        )

    rows = q.all()

    workers_data = []
    total_entries = 0
    total_weight = Decimal("0.000")

    for r in rows:
        worker_weight = Decimal(str(r.total_weight_kg))
        worker_weight_formatted = _format_decimal(worker_weight)
        workers_data.append(
            {
                "worker_id": r.id,
                "name": r.name,
                "barcode": r.barcode,
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
