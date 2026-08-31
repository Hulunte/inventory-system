from flask import Blueprint, jsonify, request

from app.services.inventory_service import (
    create_receipt,
    get_all_movements,
    get_product_by_barcode,
    get_stock_for_product,
)

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.post("/api/inventory/receipts")
def register_receipt():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    barcode = data.get("barcode")
    quantity = data.get("quantity")

    if not barcode or quantity is None:
        return jsonify({"error": "barcode and quantity are required"}), 400

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify({"error": "quantity must be an integer"}), 400

    if quantity <= 0:
        return jsonify({"error": "quantity must be greater than zero"}), 400

    movement = create_receipt(barcode, quantity)

    if movement is None:
        return jsonify({"error": "Product not found"}), 404

    product = movement.product

    return (
        jsonify(
            {
                "id": movement.id,
                "movement_type": movement.movement_type,
                "quantity": movement.quantity,
                "product": {
                    "id": product.id,
                    "barcode": product.barcode,
                    "name": product.name,
                },
                "created_at": movement.created_at.isoformat(),
            }
        ),
        201,
    )


@inventory_bp.get("/api/inventory/stock/<barcode>")
def get_stock(barcode):
    product = get_product_by_barcode(barcode)

    if product is None:
        return jsonify({"error": "Product not found"}), 404

    stock = get_stock_for_product(product.id)

    return jsonify(
        {
            "product": {
                "id": product.id,
                "barcode": product.barcode,
                "name": product.name,
            },
            "stock": stock,
        }
    )


@inventory_bp.get("/api/inventory/movements")
def list_movements():
    movements = get_all_movements()

    return jsonify(
        [
            {
                "id": movement.id,
                "movement_type": movement.movement_type,
                "quantity": movement.quantity,
                "created_at": movement.created_at.isoformat(),
                "product": {
                    "id": movement.product.id,
                    "barcode": movement.product.barcode,
                    "name": movement.product.name,
                },
            }
            for movement in movements
        ]
    )
