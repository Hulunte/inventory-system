from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

from app.services.harvest_service import (
    get_all_entries,
    get_daily_total,
    get_worker_by_barcode,
    register_harvest,
)

harvest_bp = Blueprint("harvest", __name__)


@harvest_bp.get("/api/products/active")
def list_active_products():
    from app.models.product import Product
    from sqlalchemy import func

    products = (
        Product.query
        .filter(Product.active == True)
        .order_by(func.lower(Product.name).asc())
        .all()
    )
    return jsonify([
        {
            "id": p.id,
            "name": p.name,
            "rate_per_kg": str(p.rate_per_kg.quantize(Decimal("0.01"))),
        }
        for p in products
    ])


@harvest_bp.post("/api/harvest/entries")
def create_entry():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    barcode = data.get("barcode")
    weight_kg_raw = data.get("weight_kg")
    product_id_raw = data.get("product_id")

    if not barcode or weight_kg_raw is None:
        return jsonify({"error": "barcode and weight_kg are required"}), 400

    if product_id_raw is None:
        return jsonify({"error": "product_id is required"}), 400

    if not isinstance(product_id_raw, int) or isinstance(product_id_raw, bool):
        return jsonify({"error": "product_id must be a positive integer"}), 400

    if product_id_raw <= 0:
        return jsonify({"error": "product_id must be a positive integer"}), 400

    try:
        weight_kg = Decimal(str(weight_kg_raw))
    except (InvalidOperation, TypeError, ValueError):
        return jsonify({"error": "weight_kg must be a valid number"}), 400

    if weight_kg <= 0:
        return jsonify({"error": "weight_kg must be greater than zero"}), 400

    entry, daily_total = register_harvest(barcode, weight_kg, product_id_raw)

    if entry is None:
        return jsonify({"error": "Worker or product not found"}), 404

    worker = entry.worker

    return (
        jsonify(
            {
                "id": entry.id,
                "weight_kg": str(entry.weight_kg),
                "worker": {
                    "id": worker.id,
                    "barcode": worker.barcode,
                    "name": worker.name,
                },
                "product_id": entry.product_id,
                "product_name": entry.product_name_snapshot,
                "rate_per_kg": str(entry.rate_per_kg_snapshot.quantize(Decimal("0.01"))) if entry.rate_per_kg_snapshot is not None else None,
                "amount_mxn": str(entry.amount_mxn.quantize(Decimal("0.01"))) if entry.amount_mxn is not None else None,
                "daily_total": str(daily_total),
                "created_at": entry.created_at.isoformat(),
            }
        ),
        201,
    )


@harvest_bp.get("/api/harvest/daily/<barcode>")
def get_daily(barcode):
    worker = get_worker_by_barcode(barcode)

    if worker is None:
        return jsonify({"error": "Worker not found"}), 404

    daily_total = get_daily_total(worker.id)

    return jsonify(
        {
            "worker": {
                "id": worker.id,
                "barcode": worker.barcode,
                "name": worker.name,
            },
            "daily_total": str(daily_total),
        }
    )


@harvest_bp.get("/api/harvest/entries")
def list_entries():
    entries = get_all_entries()

    return jsonify(
        [
            {
                "id": entry.id,
                "weight_kg": str(entry.weight_kg),
                "worker": {
                    "id": entry.worker.id,
                    "barcode": entry.worker.barcode,
                    "name": entry.worker.name,
                },
                "product_id": entry.product_id,
                "product_name": entry.product_name_snapshot,
                "rate_per_kg": str(entry.rate_per_kg_snapshot.quantize(Decimal("0.01"))) if entry.rate_per_kg_snapshot is not None else None,
                "amount_mxn": str(entry.amount_mxn.quantize(Decimal("0.01"))) if entry.amount_mxn is not None else None,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in entries
        ]
    )
