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

    workers_data = [
        {
            "worker_id": r.id,
            "name": r.name,
            "barcode": r.barcode,
            "entries_count": r.entries_count,
            "total_weight_kg": str(Decimal(str(r.total_weight_kg))),
        }
        for r in rows
    ]

    total_entries = 0
    total_weight = Decimal("0.000")

    for row in workers_data:
        total_entries += row["entries_count"]
        total_weight += Decimal(row["total_weight_kg"])

    return {
        "workers": workers_data,
        "summary": {
            "total_entries": total_entries,
            "total_weight_kg": str(total_weight),
        },
    }


def get_worker_entries(worker_id, operational_date, tz=None):
    if tz is None:
        tz = _get_tz()
    start_utc, end_utc = _date_range_to_utc(operational_date, tz)

    entries = (
        HarvestEntry.query
        .filter(
            HarvestEntry.worker_id == worker_id,
            HarvestEntry.created_at >= start_utc,
            HarvestEntry.created_at < end_utc,
        )
        .order_by(HarvestEntry.created_at.asc())
        .all()
    )

    return entries
