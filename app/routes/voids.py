from flask import Blueprint, current_app, jsonify, request, session

from app.services.void_service import get_voided_entries


voids_bp = Blueprint("voids", __name__)


@voids_bp.before_request
def require_voids_admin():
    if not session.get("admin"):
        return jsonify({"error": "Admin authentication required"}), 401
    return None


@voids_bp.get("/api/voids")
def list_voided_entries():
    query_filter = request.args.get("q", "").strip() or None
    timezone = current_app.config["HARVEST_TIMEZONE"]
    entries = get_voided_entries(query_filter)

    data = []
    for entry in entries:
        created_local = entry.created_at.astimezone(timezone)
        voided_local = entry.voided_at.astimezone(timezone)
        slot_number = entry.worker_slot_number_snapshot
        data.append(
            {
                "id": entry.id,
                "worker_assignment_id": entry.worker_assignment_id,
                "worker_name": entry.worker_name_snapshot,
                "worker_barcode": entry.worker_barcode_snapshot,
                "slot_number": slot_number,
                "slot_label": (
                    f"Trabajador {slot_number:03d}" if slot_number else None
                ),
                "product_name": entry.product_name_snapshot,
                "date": created_local.strftime("%d/%m/%Y"),
                "time": created_local.strftime("%H:%M:%S"),
                "weight_kg": str(entry.weight_kg),
                "amount_mxn": (
                    str(entry.amount_mxn) if entry.amount_mxn is not None else None
                ),
                "void_reason": entry.void_reason,
                "voided_at": voided_local.strftime("%d/%m/%Y %H:%M:%S"),
                "registration_type_label": "Arpillas" if entry.registration_type == "sacks" else "Báscula",
                "sack_count": entry.sack_count,
                "average_sack_weight_kg": str(entry.average_sack_weight_kg_snapshot) if entry.average_sack_weight_kg_snapshot is not None else None,
                "estimated_weight": entry.registration_type == "sacks",
            }
        )

    return jsonify({"entries": data})
