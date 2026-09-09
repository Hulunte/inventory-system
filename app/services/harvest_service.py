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


ANONYMOUS_WORKER_NAME = "Sin nombre"


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
        open_assignment = WorkerAssignment(
            worker_id=worker.id,
            person_name=ANONYMOUS_WORKER_NAME,
        )
        db.session.add(open_assignment)
        db.session.flush()

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
        worker_name_snapshot=open_assignment.person_name or ANONYMOUS_WORKER_NAME,
    )

    db.session.add(entry)
    db.session.commit()

    daily_total = get_daily_total(open_assignment.id)
    return entry, daily_total


def register_sack_harvest(barcode, sack_count, product_id):
    """Register an estimated movement using the product's configured sack average."""
    _validate_product_id(product_id)
    worker = (
        db.session.query(Worker)
        .filter(Worker.barcode == barcode, Worker.active.is_(True))
        .with_for_update()
        .one_or_none()
    )
    if worker is None:
        return None, None
    assignment = (
        WorkerAssignment.query.filter_by(worker_id=worker.id, ended_at=None)
        .with_for_update().one_or_none()
    )
    if assignment is None:
        raise WorkerUnassignedError("Este cupo no tiene una persona asignada.")
    product = (
        Product.query.filter(Product.id == product_id, Product.active.is_(True))
        .with_for_update().one_or_none()
    )
    if product is None:
        raise ProductUnavailableError("El producto seleccionado ya no está disponible.")
    if product.average_sack_weight_kg is None:
        raise ValueError("Promedio no disponible")

    average = Decimal(str(product.average_sack_weight_kg))
    estimated_weight = (Decimal(sack_count) * average).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    rate = Decimal(str(product.rate_per_kg))
    amount = (estimated_weight * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    entry = HarvestEntry(
        worker_id=worker.id,
        worker_assignment_id=assignment.id,
        worker_slot_number_snapshot=worker.slot_number,
        worker_barcode_snapshot=worker.barcode,
        worker_name_snapshot=assignment.person_name,
        product_id=product.id,
        product_name_snapshot=product.name,
        rate_per_kg_snapshot=rate,
        weight_kg=estimated_weight,
        amount_mxn=amount,
        registration_type="sacks",
        sack_count=sack_count,
        average_sack_weight_kg_snapshot=average,
    )
    db.session.add(entry)
    db.session.commit()
    return entry, get_daily_total(assignment.id)


def get_sack_statistics(product_id):
    from app.services.product_service import get_active_products_for_reception

    product = next(
        (item for item in get_active_products_for_reception() if item["id"] == product_id),
        None,
    )
    if product is None:
        return None
    stats = product["sack_statistics"]
    return {
        "available": product["average_sack_weight_kg"] is not None,
        "configured_average_kg_per_sack": product["average_sack_weight_kg"],
        **stats,
    }


def get_daily_total(assignment_id, operational_date=None, tz=None):
    if assignment_id is None:
        return Decimal("0")
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


def get_recent_movements(limit=10, can_void=False):
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
                "name": entry.worker_name_snapshot or ANONYMOUS_WORKER_NAME,
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
            "registration_type": entry.registration_type,
            "registration_type_label": "Arpillas" if entry.registration_type == "sacks" else "Báscula",
            "sack_count": entry.sack_count,
            "average_sack_weight_kg": str(entry.average_sack_weight_kg_snapshot) if entry.average_sack_weight_kg_snapshot is not None else None,
            "estimated_weight": entry.registration_type == "sacks",
            "can_void": bool(can_void),
        })

    return movements


def _date_range_to_utc(start_date, tz):
    start_utc = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(timezone.utc)
    end_utc = datetime.combine(start_date + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    return start_utc, end_utc
