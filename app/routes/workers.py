from flask import Blueprint, jsonify
from app.models.worker import Worker
from app.services.worker_slot_service import get_open_assignment

workers_bp = Blueprint("workers", __name__)


@workers_bp.get("/api/workers/<barcode>")
def get_worker_by_barcode(barcode):
    worker = Worker.query.filter_by(barcode=barcode, active=True).first()

    if worker is None:
        return jsonify({"error": "Worker not found"}), 404

    assignment = get_open_assignment(worker.id)

    return jsonify(
        {
            "id": worker.id,
            "barcode": worker.barcode,
            "name": worker.name,
            "active": worker.active,
            "slot_number": worker.slot_number,
            "slot_label": worker.slot_label,
            "has_assignment": assignment is not None,
            "person_name": assignment.person_name if assignment else None,
        }
    )
