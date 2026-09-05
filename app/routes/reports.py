import re
import secrets
import smtplib

from flask import Blueprint, Response, current_app, jsonify, request, session
from functools import wraps

from app.services.email_service import SMTPConfigError, send_export_email
from app.services.export_service import generate_harvest_export
from app.services.report_service import get_harvest_report, parse_date

reports_bp = Blueprint("reports", __name__)

_ADMIN_MUTATING = {"POST", "PATCH", "PUT", "DELETE"}

_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9]"
    r"[a-zA-Z0-9._%+\-]*"
    r"@[a-zA-Z0-9]"
    r"[a-zA-Z0-9.\-]*"
    r"\.[a-zA-Z]{2,}$"
)


def _require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"error": "Admin authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


def _require_csrf(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in _ADMIN_MUTATING:
            token = request.headers.get("X-CSRF-Token")
            if not token or not secrets.compare_digest(token, session.get("csrf_token", "")):
                return jsonify({"error": "CSRF token invalid"}), 403
        return f(*args, **kwargs)
    return decorated


def _validate_email(value):
    """Validate a single email address. Returns the stripped email or None."""
    if not isinstance(value, str):
        return None
    email = value.strip()
    if not email:
        return None
    if len(email) > 254:
        return None
    if "\r" in email or "\n" in email:
        return None
    if " " in email or "\t" in email:
        return None
    if "," in email or ";" in email:
        return None
    if email.startswith("<") or email.endswith(">"):
        return None
    if "<" in email or ">" in email:
        return None
    if not _EMAIL_RE.match(email):
        return None
    return email


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
@_require_admin
def harvest_export():
    start_date, end_date, error = _validate_date_params()
    if error:
        return error

    query_filter = request.args.get("q", "").strip() or None
    tz = current_app.config["HARVEST_TIMEZONE"]

    xlsx_bytes, filename = generate_harvest_export(start_date, end_date, query_filter, tz)

    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@reports_bp.post("/api/reports/harvest/export/email")
@_require_admin
@_require_csrf
def harvest_export_email():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    KNOWN_FIELDS = {"email", "start_date", "end_date", "q"}
    unknown = set(data.keys()) - KNOWN_FIELDS
    if unknown:
        return jsonify({"error": f"Unknown fields: {', '.join(sorted(unknown))}"}), 400

    email = _validate_email(data.get("email"))
    if email is None:
        return jsonify({"error": "Invalid email address"}), 400

    start_date_str = data.get("start_date")
    end_date_str = data.get("end_date")

    if not start_date_str or not end_date_str:
        return jsonify({"error": "start_date and end_date are required"}), 400

    start_date = parse_date(start_date_str)
    if start_date is None:
        return jsonify({"error": "Invalid start_date format. Use YYYY-MM-DD."}), 400

    end_date = parse_date(end_date_str)
    if end_date is None:
        return jsonify({"error": "Invalid end_date format. Use YYYY-MM-DD."}), 400

    if start_date > end_date:
        return jsonify({"error": "start_date must not be after end_date."}), 400

    query_filter = (data.get("q") or "").strip() or None
    tz = current_app.config["HARVEST_TIMEZONE"]

    xlsx_bytes, filename = generate_harvest_export(start_date, end_date, query_filter, tz)

    if not xlsx_bytes:
        return jsonify({"error": "Generated export is empty"}), 500

    try:
        send_export_email(email, filename, xlsx_bytes, current_app.config)
    except SMTPConfigError:
        return jsonify({"error": "Email service not configured"}), 503
    except smtplib.SMTPException:
        return jsonify({"error": "Failed to send email"}), 502
    except OSError:
        return jsonify({"error": "Failed to send email"}), 502

    return jsonify({"message": f"Correo enviado a {email}"})
