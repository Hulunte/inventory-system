from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

from app.services.harvest_service import (
    get_all_entries,
    get_daily_total,
    get_worker_by_barcode,
    register_harvest,
)

harvest_bp = Blueprint("harvest", __name__)


@harvest_bp.post("/api/harvest/entries")
def create_entry():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    barcode = data.get("barcode")
    weight_kg_raw = data.get("weight_kg")

    if not barcode or weight_kg_raw is None:
        return jsonify({"error": "barcode and weight_kg are required"}), 400

    try:
        weight_kg = Decimal(str(weight_kg_raw))
    except (InvalidOperation, TypeError, ValueError):
        return jsonify({"error": "weight_kg must be a valid number"}), 400

    if weight_kg <= 0:
        return jsonify({"error": "weight_kg must be greater than zero"}), 400

    entry, daily_total = register_harvest(barcode, weight_kg)

    if entry is None:
        return jsonify({"error": "Worker not found"}), 404

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
                "created_at": entry.created_at.isoformat(),
            }
            for entry in entries
        ]
    )
