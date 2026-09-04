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


def serialize_product(product):
    return {
        "id": product.id,
        "name": product.name,
        "rate_per_kg": _format_rate(product.rate_per_kg),
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


def create_product(name, rate_per_kg):
    name = _validate_name(name)
    rate_per_kg = _validate_rate(rate_per_kg)

    existing = Product.query.filter(
        func.lower(Product.name) == name.lower()
    ).first()
    if existing:
        raise DuplicateProductError("El producto ya existe.")

    product = Product(name=name, rate_per_kg=rate_per_kg)
    db.session.add(product)
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        if _is_duplicate_product_name_error(e):
            raise DuplicateProductError("El producto ya existe.")
        raise
    return product


def update_product(product_id, name=None, rate_per_kg=None):
    product = db.session.get(Product, product_id)
    if product is None:
        return None

    if name is not None:
        name = _validate_name(name)
        product.name = name
    if rate_per_kg is not None:
        rate_per_kg = _validate_rate(rate_per_kg)
        product.rate_per_kg = rate_per_kg

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
    products = (
        Product.query
        .filter(Product.active.is_(True))
        .order_by(func.lower(Product.name).asc())
        .all()
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            "rate_per_kg": _format_rate(p.rate_per_kg),
        }
        for p in products
    ]
