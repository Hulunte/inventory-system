from flask import Blueprint, jsonify
from app.models.worker import Worker

workers_bp = Blueprint("workers", __name__)


@workers_bp.get("/api/workers/<barcode>")
def get_worker_by_barcode(barcode):
    worker = Worker.query.filter_by(barcode=barcode, active=True).first()

    if worker is None:
        return jsonify({"error": "Worker not found"}), 404

    return jsonify(
        {
            "id": worker.id,
            "barcode": worker.barcode,
            "name": worker.name,
            "active": worker.active,
        }
    )
