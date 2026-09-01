from flask import Blueprint, current_app, jsonify, request

from app.services.report_service import get_harvest_report, parse_date

reports_bp = Blueprint("reports", __name__)


@reports_bp.get("/api/reports/harvest")
def harvest_report():
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    query_filter = request.args.get("q", "").strip() or None

    if not start_date_str and not end_date_str:
        return jsonify({"error": "start_date and end_date are required."}), 400

    if not start_date_str:
        return jsonify({"error": "start_date is required."}), 400

    if not end_date_str:
        return jsonify({"error": "end_date is required."}), 400

    start_date = parse_date(start_date_str)
    if start_date is None:
        return jsonify({"error": "Invalid start_date format. Use YYYY-MM-DD."}), 400

    end_date = parse_date(end_date_str)
    if end_date is None:
        return jsonify({"error": "Invalid end_date format. Use YYYY-MM-DD."}), 400

    if start_date > end_date:
        return jsonify({"error": "start_date must not be after end_date."}), 400

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
