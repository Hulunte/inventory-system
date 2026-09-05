from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func

from app.exceptions import ProductUnavailableError
from app.extensions import db
from app.models.harvest_entry import HarvestEntry
from app.models.product import Product
from app.models.worker import Worker
from app.models.worker_assignment import WorkerAssignment


class WorkerUnassignedError(Exception):
    """Raised when a worker has no open assignment."""


def get_worker_by_barcode(barcode):
    return Worker.query.filter_by(barcode=barcode, active=True).first()


def _validate_product_id(product_id):
    if isinstance(product_id, bool):
        raise ValueError("product_id must be a valid integer")
    if not isinstance(product_id, int):
        raise ValueError("product_id must be a valid integer")
    if product_id <= 0:
        raise ValueError("product_id must be a positive integer")


def register_harvest(barcode, weight_kg, product_id):
    _validate_product_id(product_id)

    worker = (
        db.session.query(Worker)
        .filter(Worker.barcode == barcode, Worker.active.is_(True))
        .with_for_update()
        .one_or_none()
    )

    if worker is None:
        worker_inactive = Worker.query.filter_by(barcode=barcode).first()
        if worker_inactive is not None:
            return None, None
        return None, None

    open_assignment = (
        WorkerAssignment.query
        .filter_by(worker_id=worker.id, ended_at=None)
        .with_for_update()
        .one_or_none()
    )

    if open_assignment is None:
        raise WorkerUnassignedError("worker_unassigned")

    product = (
        Product.query
        .filter(Product.id == product_id, Product.active.is_(True))
        .with_for_update()
        .one_or_none()
    )

    if product is None:
        raise ProductUnavailableError(
            "El producto seleccionado ya no está disponible."
        )

    rate_snapshot = Decimal(str(product.rate_per_kg))
    amount = (weight_kg * rate_snapshot).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    entry = HarvestEntry(
        worker_id=worker.id,
        weight_kg=weight_kg,
        product_id=product.id,
        product_name_snapshot=product.name,
        rate_per_kg_snapshot=rate_snapshot,
        amount_mxn=amount,
        worker_assignment_id=open_assignment.id,
        worker_slot_number_snapshot=worker.slot_number,
        worker_barcode_snapshot=worker.barcode,
        worker_name_snapshot=open_assignment.person_name,
    )

    db.session.add(entry)
    db.session.commit()

    daily_total = get_daily_total(open_assignment.id)
    return entry, daily_total


def get_daily_total(assignment_id, operational_date=None, tz=None):
    if operational_date is None:
        if tz is None:
            from flask import current_app
            tz = current_app.config["HARVEST_TIMEZONE"]
        operational_date = datetime.now(tz).date()

    start_of_day = datetime.combine(operational_date, time.min, tzinfo=tz)
    end_of_day = start_of_day + timedelta(days=1)

    start_utc = start_of_day.astimezone(timezone.utc)
    end_utc = end_of_day.astimezone(timezone.utc)

    total = (
        db.session.query(func.coalesce(func.sum(HarvestEntry.weight_kg), 0))
        .filter(
            HarvestEntry.worker_assignment_id == assignment_id,
            HarvestEntry.created_at >= start_utc,
            HarvestEntry.created_at < end_utc,
            HarvestEntry.voided == False,
        )
        .scalar()
    )

    return Decimal(str(total))


def get_all_entries():
    return (
        HarvestEntry.query
        .filter_by(voided=False)
        .order_by(HarvestEntry.created_at.desc())
        .all()
    )


def get_recent_movements(limit=10):
    from flask import current_app
    tz = current_app.config["HARVEST_TIMEZONE"]

    operational_date = datetime.now(tz).date()
    start_utc, end_utc = _date_range_to_utc(operational_date, tz)

    entries = (
        HarvestEntry.query
        .filter(
            HarvestEntry.created_at >= start_utc,
            HarvestEntry.created_at < end_utc,
        )
        .order_by(HarvestEntry.created_at.desc(), HarvestEntry.id.desc())
        .limit(limit)
        .all()
    )

    movements = []
    for entry in entries:
        local_time = entry.created_at.astimezone(tz).strftime("%H:%M:%S")
        slot_num = entry.worker_slot_number_snapshot
        movements.append({
            "id": entry.id,
            "time": local_time,
            "worker": {
                "name": entry.worker_name_snapshot,
                "barcode": entry.worker_barcode_snapshot,
                "slot_number": slot_num,
                "slot_label": f"Trabajador {slot_num:03d}" if slot_num is not None else None,
            },
            "worker_assignment_id": entry.worker_assignment_id,
            "product_name": entry.product_name_snapshot,
            "weight_kg": str(entry.weight_kg),
            "rate_per_kg": (
                str(entry.rate_per_kg_snapshot.quantize(Decimal("0.01")))
                if entry.rate_per_kg_snapshot is not None
                else None
            ),
            "amount_mxn": (
                str(entry.amount_mxn.quantize(Decimal("0.01")))
                if entry.amount_mxn is not None
                else None
            ),
            "voided": entry.voided,
        })

    return movements


def _date_range_to_utc(start_date, tz):
    start_utc = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(timezone.utc)
    end_utc = datetime.combine(start_date + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    return start_utc, end_utc
