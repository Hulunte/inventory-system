from decimal import Decimal, InvalidOperation

import secrets
from flask import Blueprint, jsonify, make_response, request, session

from app.exceptions import ProductUnavailableError
from app.services.harvest_service import (
    ANONYMOUS_WORKER_NAME,
    WorkerUnassignedError,
    get_all_entries,
    get_daily_total,
    get_recent_movements,
    get_worker_by_barcode,
    register_harvest,
    register_sack_harvest,
    get_sack_statistics,
)
from app.services.product_service import get_active_products_for_reception

harvest_bp = Blueprint("harvest", __name__)

_ALLOWED_ENTRY_FIELDS = {"barcode", "weight_kg", "product_id"}


def _validate_admin_csrf():
    if not session.get("admin"):
        return jsonify({"error": "Admin authentication required"}), 401
    token = request.headers.get("X-CSRF-Token", "")
    if not token or not secrets.compare_digest(token, session.get("csrf_token", "")):
        return jsonify({"error": "CSRF token invalid"}), 403
    return None


def _format_snapshot_value(value):
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01")))


@harvest_bp.get("/api/products/active")
def list_active_products():
    return jsonify(get_active_products_for_reception())


@harvest_bp.post("/api/harvest/entries")
def create_entry():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Cuerpo JSON inválido"}), 400

    unknown = set(data.keys()) - _ALLOWED_ENTRY_FIELDS
    if unknown:
        return jsonify({"error": f"Campos desconocidos: {', '.join(sorted(unknown))}"}), 400

    barcode = data.get("barcode")
    weight_kg_raw = data.get("weight_kg")
    product_id_raw = data.get("product_id")

    if not barcode or weight_kg_raw is None:
        return jsonify({"error": "barcode and weight_kg are required"}), 400

    if product_id_raw is None:
        return jsonify({"error": "product_id is required"}), 400

    if isinstance(product_id_raw, bool) or not isinstance(product_id_raw, int):
        return jsonify({"error": "product_id must be a positive integer"}), 400

    if product_id_raw <= 0:
        return jsonify({"error": "product_id must be a positive integer"}), 400

    if isinstance(weight_kg_raw, bool):
        return jsonify({"error": "weight_kg must be a valid number"}), 400

    try:
        weight_kg = Decimal(str(weight_kg_raw))
    except (InvalidOperation, TypeError, ValueError):
        return jsonify({"error": "weight_kg must be a valid number"}), 400

    if weight_kg.is_nan() or weight_kg.is_infinite():
        return jsonify({"error": "weight_kg must be a valid number"}), 400

    if weight_kg <= 0:
        return jsonify({"error": "weight_kg must be greater than zero"}), 400

    if weight_kg.as_tuple().exponent < -3:
        return jsonify({"error": "weight_kg must have at most 3 decimal places"}), 400

    try:
        entry, daily_total = register_harvest(barcode, weight_kg, product_id_raw)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except ProductUnavailableError:
        return jsonify({
            "error": "El producto seleccionado ya no está disponible.",
            "code": "product_unavailable",
        }), 409
    except WorkerUnassignedError:
        return jsonify({
            "error": "Este cupo no tiene una persona asignada.",
            "code": "worker_unassigned",
        }), 409

    if entry is None:
        return jsonify({"error": "Trabajador no encontrado"}), 404

    worker = entry.worker

    return (
        jsonify(
            {
                "id": entry.id,
                "weight_kg": str(entry.weight_kg),
                "worker": {
                    "id": worker.id,
                    "barcode": entry.worker_barcode_snapshot or worker.barcode,
                    "name": entry.worker_name_snapshot or worker.name,
                    "slot_number": entry.worker_slot_number_snapshot or worker.slot_number,
                    "slot_label": f"Trabajador {(entry.worker_slot_number_snapshot or worker.slot_number):03d}",
                },
                "product_id": entry.product_id,
                "product_name": entry.product_name_snapshot,
                "rate_per_kg": _format_snapshot_value(entry.rate_per_kg_snapshot),
                "measurement_mode": "scale",
                "registration_type_label": "Báscula",
                "amount_mxn": _format_snapshot_value(entry.amount_mxn),
                "daily_total": str(daily_total),
                "created_at": entry.created_at.isoformat(),
            }
        ),
        201,
    )


@harvest_bp.post("/api/harvest/sack-entries")
def create_sack_entry():
    auth_error = _validate_admin_csrf()
    if auth_error:
        return auth_error
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Cuerpo JSON inválido"}), 400
    unknown = set(data) - {"barcode", "product_id", "sack_count"}
    if unknown:
        return jsonify({"error": f"Campos desconocidos: {', '.join(sorted(unknown))}"}), 400
    barcode = data.get("barcode")
    product_id = data.get("product_id")
    sack_count = data.get("sack_count")
    if not isinstance(barcode, str) or not barcode.strip():
        return jsonify({"error": "barcode is required"}), 400
    if isinstance(product_id, bool) or not isinstance(product_id, int) or product_id <= 0:
        return jsonify({"error": "product_id must be a positive integer"}), 400
    if isinstance(sack_count, bool) or not isinstance(sack_count, int) or sack_count <= 0:
        return jsonify({"error": "La cantidad de arpillas debe ser un entero positivo"}), 400
    try:
        entry, daily_total = register_sack_harvest(barcode.strip(), sack_count, product_id)
    except ProductUnavailableError:
        return jsonify({"error": "El producto seleccionado ya no está disponible."}), 409
    except WorkerUnassignedError as exc:
        return jsonify({"error": str(exc), "code": "worker_unassigned"}), 409
    except ValueError as exc:
        return jsonify({"error": str(exc), "code": "average_unavailable"}), 409
    if entry is None:
        return jsonify({"error": "Trabajador no encontrado"}), 404
    return jsonify({
        "id": entry.id,
        "worker_assignment_id": entry.worker_assignment_id,
        "registration_type": "sacks",
        "measurement_mode": "sacks",
        "registration_type_label": "Arpillas",
        "sack_count": entry.sack_count,
        "weight_kg": str(entry.weight_kg),
        "estimated_weight": True,
        "average_sack_weight_kg": str(entry.average_sack_weight_kg_snapshot),
        "rate_per_sack": _format_snapshot_value(entry.rate_per_sack_snapshot),
        "price_per_sack_snapshot": _format_snapshot_value(entry.price_per_sack_snapshot),
        "amount_mxn": _format_snapshot_value(entry.amount_mxn),
        "daily_total": str(daily_total),
        "product_name": entry.product_name_snapshot,
    }), 201


@harvest_bp.get("/api/harvest/sack-statistics/<int:product_id>")
def sack_statistics(product_id):
    auth_error = _validate_admin_csrf()
    if auth_error:
        return auth_error
    result = get_sack_statistics(product_id)
    if result is None:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify(result)


@harvest_bp.get("/api/harvest/daily/<barcode>")
def get_daily(barcode):
    worker = get_worker_by_barcode(barcode)

    if worker is None:
        return jsonify({"error": "Worker not found"}), 404

    from app.models.worker_assignment import WorkerAssignment
    open_assignment = WorkerAssignment.query.filter_by(
        worker_id=worker.id, ended_at=None
    ).first()

    daily_total = get_daily_total(open_assignment.id) if open_assignment else Decimal("0")

    return jsonify(
        {
            "worker": {
                "id": worker.id,
                "barcode": worker.barcode,
                "name": open_assignment.person_name if open_assignment else ANONYMOUS_WORKER_NAME,
                "slot_number": worker.slot_number,
                "slot_label": worker.slot_label,
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
                    "barcode": entry.worker_barcode_snapshot or entry.worker.barcode,
                    "name": entry.worker_name_snapshot or entry.worker.name,
                    "slot_number": entry.worker_slot_number_snapshot or entry.worker.slot_number,
                    "slot_label": f"Trabajador {(entry.worker_slot_number_snapshot or entry.worker.slot_number):03d}",
                },
                "product_id": entry.product_id,
                "product_name": entry.product_name_snapshot,
                "rate_per_kg": _format_snapshot_value(entry.rate_per_kg_snapshot),
                "amount_mxn": _format_snapshot_value(entry.amount_mxn),
                "created_at": entry.created_at.isoformat(),
            }
            for entry in entries
        ]
    )


@harvest_bp.get("/api/harvest/recent")
def list_recent_movements():
    limit_raw = request.args.get("limit", "10")

    if isinstance(limit_raw, bool):
        return jsonify({"error": "limit must be a positive integer"}), 400

    if not isinstance(limit_raw, str):
        return jsonify({"error": "limit must be a positive integer"}), 400

    if limit_raw != limit_raw.strip():
        return jsonify({"error": "limit must be a positive integer"}), 400

    limit_raw = limit_raw.strip()

    if not limit_raw:
        return jsonify({"error": "limit must be a positive integer"}), 400

    try:
        limit = int(limit_raw)
    except (ValueError, TypeError):
        return jsonify({"error": "limit must be a positive integer"}), 400

    if str(limit) != limit_raw:
        return jsonify({"error": "limit must be a positive integer"}), 400

    if limit < 1 or limit > 20:
        return jsonify({"error": "limit must be between 1 and 20"}), 400

    movements = get_recent_movements(limit=limit, can_void=bool(session.get("admin")))
    response = make_response(jsonify({"movements": movements}))
    response.headers["Cache-Control"] = "no-store"
    return response
