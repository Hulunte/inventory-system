from datetime import datetime
from decimal import Decimal

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models.worker import Worker
from app.services.history_service import (
    get_daily_summary,
    get_worker_entries,
    parse_date,
)

history_bp = Blueprint("history", __name__)


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


@history_bp.get("/api/history/workers/<int:worker_id>/entries")
def worker_entries(worker_id):
    worker = db.session.get(Worker, worker_id)

    if worker is None:
        return jsonify({"error": "Worker not found"}), 404

    date_str = request.args.get("date")

    if date_str:
        operational_date = parse_date(date_str)
        if operational_date is None:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
    else:
        tz = current_app.config["HARVEST_TIMEZONE"]
        operational_date = datetime.now(tz).date()

    tz = current_app.config["HARVEST_TIMEZONE"]
    entries = get_worker_entries(worker_id, operational_date, tz)

    serialized = []
    for entry in entries:
        local_dt = entry.created_at.astimezone(tz)
        serialized.append(
            {
                "id": entry.id,
                "weight_kg": str(entry.weight_kg),
                "created_at": local_dt.strftime("%H:%M"),
            }
        )

    total_weight = sum(
        (Decimal(str(e["weight_kg"])) for e in serialized),
        Decimal("0.000"),
    )

    return jsonify(
        {
            "date": operational_date.isoformat(),
            "worker": {
                "id": worker.id,
                "name": worker.name,
                "barcode": worker.barcode,
            },
            "entries": serialized,
            "summary": {
                "entries_count": len(serialized),
                "total_weight_kg": str(total_weight),
            },
        }
    )
