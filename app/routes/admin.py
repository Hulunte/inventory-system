from flask import Blueprint, jsonify, request

from app.models.worker import Worker
from app.services.worker_service import (
    activate_worker,
    create_worker,
    deactivate_worker,
    get_worker_by_id,
    search_workers,
)

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/api/admin/workers")
def list_workers():
    query = request.args.get("q", "").strip() or None
    workers = search_workers(query)

    return jsonify(
        [
            {
                "id": w.id,
                "barcode": w.barcode,
                "name": w.name,
                "active": w.active,
                "created_at": w.created_at.isoformat(),
            }
            for w in workers
        ]
    )


@admin_bp.get("/api/admin/workers/<int:worker_id>")
def get_worker(worker_id):
    worker = get_worker_by_id(worker_id)

    if worker is None:
        return jsonify({"error": "Worker not found"}), 404

    return jsonify(
        {
            "id": worker.id,
            "barcode": worker.barcode,
            "name": worker.name,
            "active": worker.active,
            "created_at": worker.created_at.isoformat(),
        }
    )


@admin_bp.post("/api/admin/workers")
def create():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    name = (data.get("name") or "").strip()
    barcode = (data.get("barcode") or "").strip()

    if not name:
        return jsonify({"error": "name is required"}), 400

    if not barcode:
        return jsonify({"error": "barcode is required"}), 400

    existing = Worker.query.filter_by(barcode=barcode).first()

    if existing:
        return jsonify({"error": "Barcode already exists"}), 409

    worker = create_worker(name=name, barcode=barcode)

    return (
        jsonify(
            {
                "id": worker.id,
                "barcode": worker.barcode,
                "name": worker.name,
                "active": worker.active,
                "created_at": worker.created_at.isoformat(),
            }
        ),
        201,
    )


@admin_bp.patch("/api/admin/workers/<int:worker_id>/deactivate")
def deactivate(worker_id):
    worker = deactivate_worker(worker_id)

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


@admin_bp.patch("/api/admin/workers/<int:worker_id>/activate")
def activate(worker_id):
    worker = activate_worker(worker_id)

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
