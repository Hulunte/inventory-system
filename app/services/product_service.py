from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.product import Product


class DuplicateProductError(Exception):
    pass


def _validate_rate(rate_raw):
    if isinstance(rate_raw, bool):
        raise ValueError("rate_per_kg must be a number")

    if isinstance(rate_raw, str):
        rate_str = rate_raw.strip()
        if not rate_str:
            raise ValueError("rate_per_kg is required")
    elif isinstance(rate_raw, (int, Decimal)):
        rate_str = str(rate_raw)
    else:
        raise ValueError("rate_per_kg must be a number")

    try:
        rate = Decimal(rate_str)
    except InvalidOperation:
        raise ValueError("rate_per_kg is not valid")

    if rate.is_nan() or rate.is_infinite():
        raise ValueError("rate_per_kg is not valid")

    if rate < 0:
        raise ValueError("rate_per_kg must not be negative")

    if "e" in rate_str.lower() or "E" in rate_str:
        raise ValueError("rate_per_kg must not use scientific notation")

    if rate.as_tuple().exponent < -2:
        raise ValueError("rate_per_kg must have at most 2 decimal places")

    if rate > Decimal("999999.99"):
        raise ValueError("rate_per_kg is too large")

    return rate


def _format_rate(rate):
    return str(rate.quantize(Decimal("0.01")))


def _validate_optional_rate(value, field_name):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return _validate_rate(value)
    except ValueError as exc:
        raise ValueError(str(exc).replace("rate_per_kg", field_name)) from exc


def _validate_average_sack_weight(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError("average_sack_weight_kg must be a positive number")
    try:
        average = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("average_sack_weight_kg must be a positive number")
    if not average.is_finite() or average <= 0:
        raise ValueError("average_sack_weight_kg must be greater than zero")
    if average.as_tuple().exponent < -3:
        raise ValueError("average_sack_weight_kg must have at most 3 decimal places")
    return average


def serialize_product(product):
    return {
        "id": product.id,
        "name": product.name,
        "rate_per_kg": _format_rate(product.rate_per_kg),
        "average_sack_weight_kg": (
            str(product.average_sack_weight_kg.quantize(Decimal("0.001")))
            if product.average_sack_weight_kg is not None else None
        ),
        "rate_per_sack": _format_rate(product.rate_per_sack) if product.rate_per_sack is not None else None,
        "active": product.active,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


def search_products(query=None):
    q = Product.query
    if query:
        pattern = f"%{query}%"
        q = q.filter(Product.name.ilike(pattern))
    return q.order_by(func.lower(Product.name).asc()).all()


def _validate_name(name):
    if not isinstance(name, str):
        raise ValueError("name must be a string")
    name = name.strip()
    if not name:
        raise ValueError("name is required")
    if len(name) > 100:
        raise ValueError("name is too long")
    return name


def _is_duplicate_product_name_error(error):
    diag = getattr(getattr(error, "orig", None), "diag", None)
    return getattr(diag, "constraint_name", None) == "ux_products_name_lower"


def create_product(name, rate_per_kg, average_sack_weight_kg=None, rate_per_sack=None):
    name = _validate_name(name)
    rate_per_kg = _validate_rate(rate_per_kg)
    average_sack_weight_kg = _validate_average_sack_weight(average_sack_weight_kg)
    rate_per_sack = _validate_optional_rate(rate_per_sack, "rate_per_sack")

    existing = Product.query.filter(
        func.lower(Product.name) == name.lower()
    ).first()
    if existing:
        raise DuplicateProductError("El producto ya existe.")

    product = Product(name=name, rate_per_kg=rate_per_kg, average_sack_weight_kg=average_sack_weight_kg, rate_per_sack=rate_per_sack)
    db.session.add(product)
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        if _is_duplicate_product_name_error(e):
            raise DuplicateProductError("El producto ya existe.")
        raise
    return product


def update_product(product_id, name=None, rate_per_kg=None, average_sack_weight_kg=..., rate_per_sack=...):
    product = db.session.get(Product, product_id)
    if product is None:
        return None

    if name is not None:
        name = _validate_name(name)
        product.name = name
    if rate_per_kg is not None:
        rate_per_kg = _validate_rate(rate_per_kg)
        product.rate_per_kg = rate_per_kg
    if average_sack_weight_kg is not ...:
        product.average_sack_weight_kg = _validate_average_sack_weight(average_sack_weight_kg)
    if rate_per_sack is not ...:
        product.rate_per_sack = _validate_optional_rate(rate_per_sack, "rate_per_sack")

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        if _is_duplicate_product_name_error(e):
            raise DuplicateProductError("El producto ya existe.")
        raise
    return product


def activate_product(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        return None
    product.active = True
    db.session.commit()
    return product


def deactivate_product(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        return None
    product.active = False
    db.session.commit()
    return product


def get_active_products_for_reception():
    from app.models.harvest_entry import HarvestEntry

    sack_stats = (
        db.session.query(
            HarvestEntry.product_id.label("product_id"),
            func.count(HarvestEntry.id).label("total_movements"),
            func.coalesce(func.sum(HarvestEntry.sack_count), 0).label("total_sacks"),
            func.coalesce(func.sum(HarvestEntry.weight_kg), 0).label("total_kg"),
            func.coalesce(func.sum(HarvestEntry.amount_mxn), 0).label("total_amount"),
            func.min(HarvestEntry.created_at).label("period_start"),
            func.max(HarvestEntry.created_at).label("period_end"),
        )
        .filter(HarvestEntry.registration_type == "sacks", HarvestEntry.voided.is_(False))
        .group_by(HarvestEntry.product_id)
        .subquery()
    )
    rows = (
        db.session.query(Product, sack_stats)
        .outerjoin(sack_stats, sack_stats.c.product_id == Product.id)
        .filter(Product.active.is_(True))
        .order_by(func.lower(Product.name).asc())
        .all()
    )
    products = []
    for row in rows:
        product = row[0]
        total_movements = int(row.total_movements or 0)
        total_sacks = int(row.total_sacks or 0)
        total_kg = Decimal(str(row.total_kg or 0))
        total_amount = Decimal(str(row.total_amount or 0))
        products.append({
            "id": product.id,
            "name": product.name,
            "rate_per_kg": _format_rate(product.rate_per_kg),
            "average_sack_weight_kg": (
                str(product.average_sack_weight_kg.quantize(Decimal("0.001")))
                if product.average_sack_weight_kg is not None else None
            ),
            "rate_per_sack": _format_rate(product.rate_per_sack) if product.rate_per_sack is not None else None,
            "sack_statistics": {
                "average_kg_per_movement": (
                    str((total_kg / total_movements).quantize(Decimal("0.001")))
                    if total_movements else None
                ),
                "average_kg_per_sack": (
                    str((total_kg / total_sacks).quantize(Decimal("0.001")))
                    if total_sacks else None
                ),
                "total_movements": total_movements,
                "total_sacks": total_sacks,
                "total_kg": str(total_kg.quantize(Decimal("0.001"))),
                "total_amount_mxn": str(total_amount.quantize(Decimal("0.01"))),
                "period": (
                    f"{row.period_start.date().isoformat()} a {row.period_end.date().isoformat()}"
                    if row.period_start and row.period_end else None
                ),
            },
        })
    return products


def has_product_movements(product_id):
    from app.models.harvest_entry import HarvestEntry
    return (
        db.session.query(HarvestEntry.id)
        .filter(HarvestEntry.product_id == product_id)
        .first()
        is not None
    )


def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        return None, "not_found"

    if product.active:
        return None, "active"

    if has_product_movements(product_id):
        return None, "has_movements"

    db.session.delete(product)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None, "integrity_error"

    return product, "deleted"
