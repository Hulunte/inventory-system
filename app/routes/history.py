from datetime import datetime
from decimal import Decimal

from flask import Blueprint, current_app, jsonify, request, session

from app.extensions import db
from app.models.worker import Worker
from app.models.worker_assignment import WorkerAssignment
from app.services.history_service import (
    get_daily_summary,
    get_worker_entries,
    parse_date,
)

history_bp = Blueprint("history", __name__)


@history_bp.before_request
def require_history_admin():
    if not session.get("admin"):
        return jsonify({"error": "Admin authentication required"}), 401
    return None


@history_bp.get("/api/history/daily")
def daily_summary():
    date_str = request.args.get("date")
    query_filter = request.args.get("q", "").strip() or None

    if date_str:
        operational_date = parse_date(date_str)
        if operational_date is None:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
    else:
        tz = current_app.config["HARVEST_TIMEZONE"]
        operational_date = datetime.now(tz).date()

    tz = current_app.config["HARVEST_TIMEZONE"]
    result = get_daily_summary(operational_date, query_filter, tz)

    return jsonify(
        {
            "date": operational_date.isoformat(),
            "summary": result["summary"],
            "workers": result["workers"],
        }
    )


@history_bp.get("/api/history/assignments/<int:assignment_id>/entries")
def assignment_entries(assignment_id):
    date_str = request.args.get("date")

    if date_str:
        operational_date = parse_date(date_str)
        if operational_date is None:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
    else:
        tz = current_app.config["HARVEST_TIMEZONE"]
        operational_date = datetime.now(tz).date()

    tz = current_app.config["HARVEST_TIMEZONE"]
    assignment = db.session.get(WorkerAssignment, assignment_id)
    if assignment is None:
        return jsonify({"error": "Worker assignment not found."}), 404

    entries = get_worker_entries(assignment_id, operational_date, tz)

    serialized = []
    worker_name = None
    worker_barcode = None
    slot_number = None

    for entry in entries:
        local_dt = entry.created_at.astimezone(tz)
        if worker_name is None:
            worker_name = entry.worker_name_snapshot
            worker_barcode = entry.worker_barcode_snapshot
            slot_number = entry.worker_slot_number_snapshot
        serialized.append(
            {
                "id": entry.id,
                "weight_kg": str(entry.weight_kg),
                "created_at": local_dt.strftime("%H:%M"),
                "product_name": entry.product_name_snapshot,
                "amount_mxn": str(entry.amount_mxn) if entry.amount_mxn is not None else None,
                "registration_type": entry.registration_type,
                "registration_type_label": "Arpillas" if entry.registration_type == "sacks" else "Báscula",
                "sack_count": entry.sack_count,
                "average_sack_weight_kg": str(entry.average_sack_weight_kg_snapshot) if entry.average_sack_weight_kg_snapshot is not None else None,
                "estimated_weight": entry.registration_type == "sacks",
            }
        )

    total_weight = sum(
        (Decimal(str(e["weight_kg"])) for e in serialized),
        Decimal("0.000"),
    )

    slot_label = f"Trabajador {slot_number:03d}" if slot_number else None

    return jsonify(
        {
            "date": operational_date.isoformat(),
            "worker": {
                "id": assignment.worker_id,
                "assignment_id": assignment.id,
                "name": worker_name,
                "barcode": worker_barcode,
                "slot_number": slot_number,
                "slot_label": slot_label,
            },
            "entries": serialized,
            "summary": {
                "entries_count": len(serialized),
                "total_weight_kg": str(total_weight),
            },
        }
    )
