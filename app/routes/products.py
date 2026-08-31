from flask import Blueprint, jsonify, request
from app.models.product import Product
from app.extensions import db

products_bp = Blueprint("products", __name__)


@products_bp.get("/api/products/<barcode>")
def get_product_by_barcode(barcode):
    product = Product.query.filter_by(barcode=barcode, active=True).first()

    if product is None:
        return jsonify({"error": "Product not found"}), 404

    return jsonify(
        {
            "id": product.id,
            "barcode": product.barcode,
            "name": product.name,
            "description": product.description,
            "unit": product.unit,
            "active": product.active,
        }
    )


@products_bp.get("/api/products")
def list_products():
    products = Product.query.order_by(Product.name.asc()).all()

    return jsonify(
        [
            {
                "id": product.id,
                "barcode": product.barcode,
                "name": product.name,
                "description": product.description,
                "unit": product.unit,
                "active": product.active,
            }
            for product in products
        ]
    )


from flask import request


@products_bp.post("/api/products")
def create_product():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    barcode = data.get("barcode")
    name = data.get("name")
    unit = data.get("unit", "piece")
    description = data.get("description")

    if not barcode or not name:
        return jsonify({"error": "barcode and name are required"}), 400

    existing_product = Product.query.filter_by(barcode=barcode).first()

    if existing_product:
        return jsonify({"error": "Barcode already exists"}), 409

    product = Product(barcode=barcode, name=name, unit=unit, description=description)

    from app.extensions import db

    db.session.add(product)
    db.session.commit()

    return (
        jsonify(
            {
                "id": product.id,
                "barcode": product.barcode,
                "name": product.name,
                "description": product.description,
                "unit": product.unit,
                "active": product.active,
            }
        ),
        201,
    )
