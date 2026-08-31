from sqlalchemy import func

from app.extensions import db
from app.models.product import Product
from app.models.inventory_movement import InventoryMovement


def get_product_by_barcode(barcode):
    return Product.query.filter_by(barcode=barcode, active=True).first()


def create_receipt(barcode, quantity):
    product = get_product_by_barcode(barcode)

    if product is None:
        return None

    movement = InventoryMovement(
        product_id=product.id, movement_type="RECEIPT", quantity=quantity
    )

    db.session.add(movement)
    db.session.commit()

    return movement


def get_stock_for_product(product_id):
    stock = (
        db.session.query(func.coalesce(func.sum(InventoryMovement.quantity), 0))
        .filter(InventoryMovement.product_id == product_id)
        .scalar()
    )

    return int(stock)


def get_all_movements():
    return InventoryMovement.query.order_by(InventoryMovement.created_at.desc()).all()
