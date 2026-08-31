from flask import Blueprint, jsonify, request
from app.extensions import db
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


@workers_bp.get("/api/workers")
def list_workers():
    workers = Worker.query.order_by(Worker.name.asc()).all()

    return jsonify(
        [
            {
                "id": w.id,
                "barcode": w.barcode,
                "name": w.name,
                "active": w.active,
            }
            for w in workers
        ]
    )


@workers_bp.post("/api/workers")
def create_worker():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    barcode = data.get("barcode")
    name = data.get("name")

    if not barcode or not name:
        return jsonify({"error": "barcode and name are required"}), 400

    existing = Worker.query.filter_by(barcode=barcode).first()

    if existing:
        return jsonify({"error": "Barcode already exists"}), 409

    worker = Worker(barcode=barcode, name=name)

    db.session.add(worker)
    db.session.commit()

    return (
        jsonify(
            {
                "id": worker.id,
                "barcode": worker.barcode,
                "name": worker.name,
                "active": worker.active,
            }
        ),
        201,
    )
