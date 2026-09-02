from flask import Blueprint, Response, current_app, jsonify, request

from app.routes.admin import require_admin
from app.services.export_service import generate_harvest_export
from app.services.report_service import get_harvest_report, parse_date

reports_bp = Blueprint("reports", __name__)


def _validate_date_params():
    """Validate start_date and end_date from request args. Returns (start_date, end_date, error_response)."""
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    if not start_date_str and not end_date_str:
        return None, None, (jsonify({"error": "start_date and end_date are required."}), 400)

    if not start_date_str:
        return None, None, (jsonify({"error": "start_date is required."}), 400)

    if not end_date_str:
        return None, None, (jsonify({"error": "end_date is required."}), 400)

    start_date = parse_date(start_date_str)
    if start_date is None:
        return None, None, (jsonify({"error": "Invalid start_date format. Use YYYY-MM-DD."}), 400)

    end_date = parse_date(end_date_str)
    if end_date is None:
        return None, None, (jsonify({"error": "Invalid end_date format. Use YYYY-MM-DD."}), 400)

    if start_date > end_date:
        return None, None, (jsonify({"error": "start_date must not be after end_date."}), 400)

    return start_date, end_date, None


@reports_bp.get("/api/reports/harvest")
def harvest_report():
    start_date, end_date, error = _validate_date_params()
    if error:
        return error

    query_filter = request.args.get("q", "").strip() or None
    tz = current_app.config["HARVEST_TIMEZONE"]
    result = get_harvest_report(start_date, end_date, query_filter, tz)

    return jsonify(
        {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "workers": result["workers"],
            "summary": result["summary"],
        }
    )


@reports_bp.get("/api/reports/harvest/export")
@require_admin
def harvest_export():
    start_date, end_date, error = _validate_date_params()
    if error:
        return error

    query_filter = request.args.get("q", "").strip() or None
    tz = current_app.config["HARVEST_TIMEZONE"]

    xlsx_bytes = generate_harvest_export(start_date, end_date, query_filter, tz)

    filename = f"inventario_{start_date.isoformat()}_a_{end_date.isoformat()}.xlsx"

    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
