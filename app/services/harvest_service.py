from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func

from app.extensions import db
from app.models.harvest_entry import HarvestEntry
from app.models.product import Product
from app.models.worker import Worker


def get_worker_by_barcode(barcode):
    return Worker.query.filter_by(barcode=barcode, active=True).first()


def register_harvest(barcode, weight_kg, product_id):
    worker = get_worker_by_barcode(barcode)

    if worker is None:
        return None, None

    product = db.session.get(Product, product_id)
    if product is None or not product.active:
        return None, None

    rate_snapshot = Decimal(str(product.rate_per_kg))
    amount = (weight_kg * rate_snapshot).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    entry = HarvestEntry(
        worker_id=worker.id,
        weight_kg=weight_kg,
        product_id=product.id,
        product_name_snapshot=product.name,
        rate_per_kg_snapshot=rate_snapshot,
        amount_mxn=amount,
    )

    db.session.add(entry)
    db.session.commit()

    daily_total = get_daily_total(worker.id)
    return entry, daily_total


def get_daily_total(worker_id, operational_date=None, tz=None):
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
            HarvestEntry.worker_id == worker_id,
            HarvestEntry.created_at >= start_utc,
            HarvestEntry.created_at < end_utc,
            HarvestEntry.voided == False,
        )
        .scalar()
    )

    return Decimal(str(total))


def get_all_entries():
    return HarvestEntry.query.filter_by(voided=False).order_by(HarvestEntry.created_at.desc()).all()
