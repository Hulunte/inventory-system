from decimal import Decimal

from datetime import datetime, time, timedelta, timezone

from flask import current_app
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models.harvest_entry import HarvestEntry
from app.models.worker import Worker


def verify_admin_password(password):
    password_hash = current_app.config.get("ADMIN_PASSWORD_HASH")
    if not password_hash:
        return False
    return check_password_hash(password_hash, password)


def _format_voided_at_local(voided_at_utc, tz):
    """Convert a UTC voided_at timestamp to a local DD/MM/YYYY HH:MM:SS string."""
    if voided_at_utc is None:
        return None
    return voided_at_utc.astimezone(tz).strftime("%d/%m/%Y %H:%M:%S")


def get_harvest_entries_for_admin(operational_date, query_filter=None, tz=None):
    if tz is None:
        tz = current_app.config["HARVEST_TIMEZONE"]

    start_of_day = datetime.combine(operational_date, time.min, tzinfo=tz)
    end_of_day = start_of_day + timedelta(days=1)
    start_utc = start_of_day.astimezone(timezone.utc)
    end_utc = end_of_day.astimezone(timezone.utc)

    q = (
        db.session.query(HarvestEntry, Worker)
        .join(Worker, HarvestEntry.worker_id == Worker.id)
        .filter(
            HarvestEntry.created_at >= start_utc,
            HarvestEntry.created_at < end_utc,
        )
        .order_by(HarvestEntry.created_at.desc())
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

    entries = []
    for entry, worker in rows:
        local_dt = entry.created_at.astimezone(tz)
        entry_data = {
            "id": entry.id,
            "worker": {
                "id": worker.id,
                "barcode": worker.barcode,
                "name": worker.name,
            },
            "weight_kg": str(entry.weight_kg),
            "created_at": entry.created_at.isoformat(),
            "created_at_local": local_dt.strftime("%H:%M"),
            "voided": entry.voided,
            "voided_at": entry.voided_at.isoformat() if entry.voided_at else None,
            "voided_at_local": _format_voided_at_local(entry.voided_at, tz),
            "void_reason": entry.void_reason,
            "product_id": entry.product_id,
            "product_name": entry.product_name_snapshot,
            "rate_per_kg": str(entry.rate_per_kg_snapshot.quantize(Decimal("0.01"))) if entry.rate_per_kg_snapshot is not None else None,
            "amount_mxn": str(entry.amount_mxn.quantize(Decimal("0.01"))) if entry.amount_mxn is not None else None,
        }
        entries.append(entry_data)

    return entries


def void_harvest_entry(entry_id, reason):
    entry = db.session.get(HarvestEntry, entry_id)
    if entry is None:
        return None, "not_found"

    if entry.voided:
        return entry, "already_voided"

    reason_cleaned = (reason or "").strip()
    if not reason_cleaned:
        return None, "empty_reason"

    entry.voided = True
    entry.voided_at = datetime.now(timezone.utc)
    entry.void_reason = reason_cleaned
    db.session.commit()

    return entry, "ok"
