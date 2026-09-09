import secrets
import sys
from datetime import datetime as dt
from functools import wraps

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

from app.services.report_service import parse_date
from app.services.ticket_service import (
    get_daily_tickets,
    get_single_ticket,
    serialize_daily_response,
    serialize_ticket,
)
from app.services.printer_service import (
    PrinterError,
    PrinterUnavailableError,
    get_default_printer_safe,
    get_printer_status_safe,
    is_available,
    list_printers_safe,
    print_raw,
    validate_printer_name,
)
from app.services.ticket_renderer import render_test_ticket, render_ticket

tickets_bp = Blueprint("tickets", __name__)

ADMIN_MUTATING = {"POST", "PATCH", "PUT", "DELETE"}

_PRINTER_NAME_MAX_LEN = 128


def _sanitize_printer_name(name):
    """Sanitize printer name: strip whitespace, remove null bytes, limit length."""
    if not name:
        return ""
    name = name.strip().replace("\x00", "")
    if len(name) > _PRINTER_NAME_MAX_LEN:
        return name[:_PRINTER_NAME_MAX_LEN]
    return name


def _require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Admin authentication required"}), 401
            return redirect(url_for("views.admin_login_page"))
        return f(*args, **kwargs)
    return decorated


def _require_csrf(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ADMIN_MUTATING:
            token = request.headers.get("X-CSRF-Token")
            if not token or not secrets.compare_digest(token, session.get("csrf_token", "")):
                return jsonify({"error": "CSRF token invalid"}), 403
        return f(*args, **kwargs)
    return decorated


def _operational_today():
    tz = current_app.config["HARVEST_TIMEZONE"]
    return dt.now(tz).date()


@tickets_bp.get("/tickets")
@_require_admin
def tickets_page():
    return render_template(
        "tickets.html",
        operational_today=_operational_today().isoformat(),
        csrf_token=session.get("csrf_token", ""),
    )


@tickets_bp.get("/api/tickets/daily")
@_require_admin
def api_daily_tickets():
    date_str = request.args.get("date")
    query_filter = request.args.get("q", "").strip() or None

    if query_filter and len(query_filter) > 50:
        return jsonify({"error": "El filtro de busqueda es demasiado largo (maximo 50 caracteres)"}), 400

    if date_str:
        op_date = parse_date(date_str)
        if op_date is None:
            return jsonify({"error": "Formato de fecha invalido. Use YYYY-MM-DD."}), 400
    else:
        op_date = _operational_today()

    result = get_daily_tickets(op_date, query_filter)
    return jsonify(serialize_daily_response(result))


@tickets_bp.get("/api/tickets/printers")
@_require_admin
def api_list_printers():
    available = is_available()
    printers = []
    default_name = get_default_printer_safe()

    if available:
        installed = list_printers_safe()
        for name in installed:
            printers.append({
                "name": name,
                "is_default": name == default_name,
                "status": get_printer_status_safe(name),
            })

    return jsonify({
        "direct_printing_available": available,
        "default_printer": default_name,
        "printers": printers,
    })


@tickets_bp.post("/api/tickets/printers/test")
@_require_admin
@_require_csrf
def api_test_print():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    KNOWN_FIELDS = {"printer_name"}
    unknown = set(data.keys()) - KNOWN_FIELDS
    if unknown:
        return jsonify({"error": f"Unknown fields: {', '.join(sorted(unknown))}"}), 400

    printer_name = _sanitize_printer_name(data.get("printer_name") or "")
    if not printer_name:
        return jsonify({"error": "printer_name is required"}), 400

    if not is_available():
        return jsonify({"error": "Impresion directa no disponible. Instale el controlador de impresora en Windows."}), 503

    if not validate_printer_name(printer_name):
        return jsonify({"error": "Impresora no encontrada"}), 404

    cfg = current_app.config
    now = dt.now(cfg["HARVEST_TIMEZONE"])
    print_time = now.strftime("%Y-%m-%d %H:%M:%S")

    ticket_bytes = render_test_ticket(
        business_name=cfg.get("TICKET_BUSINESS_NAME", "Sistema de Cosecha"),
        print_time_str=print_time,
        cpl=cfg.get("TICKET_CHARACTERS_PER_LINE", 48),
        encoding=cfg.get("TICKET_ENCODING", "cp850"),
        auto_cut=cfg.get("TICKET_AUTO_CUT", True),
    )

    try:
        print_raw(printer_name, ticket_bytes)
    except PrinterError as e:
        return jsonify({"error": "Error al imprimir prueba"}), 502

    return jsonify({"message": "Prueba de impresion enviada"})


@tickets_bp.post("/api/tickets/print")
@_require_admin
@_require_csrf
def api_print_ticket():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    KNOWN_FIELDS = {"date", "worker_assignment_id", "printer_name", "confirm_incomplete_amounts"}
    unknown = set(data.keys()) - KNOWN_FIELDS
    if unknown:
        return jsonify({"error": f"Unknown fields: {', '.join(sorted(unknown))}"}), 400

    date_str = data.get("date")
    if not date_str:
        return jsonify({"error": "date is required"}), 400

    op_date = parse_date(date_str)
    if op_date is None:
        return jsonify({"error": "Formato de fecha invalido. Use YYYY-MM-DD."}), 400

    assignment_id = data.get("worker_assignment_id")
    if not isinstance(assignment_id, int) or isinstance(assignment_id, bool) or assignment_id <= 0:
        return jsonify({"error": "worker_assignment_id must be a positive integer"}), 400

    printer_name = _sanitize_printer_name(data.get("printer_name") or "")
    if not printer_name:
        return jsonify({"error": "printer_name is required"}), 400

    if not is_available():
        return jsonify({"error": "Impresion directa no disponible. Instale el controlador de impresora en Windows."}), 503

    if not validate_printer_name(printer_name):
        return jsonify({"error": "Impresora no encontrada"}), 404

    ticket = get_single_ticket(op_date, assignment_id)
    if ticket is None:
        return jsonify({"error": "Ticket no encontrado para esta fecha y asignacion"}), 404

    if ticket.has_incomplete_amounts:
        confirm = data.get("confirm_incomplete_amounts")
        if confirm is not True:
            return jsonify({
                "error": "Este ticket contiene importes incompletos. Confirme con confirm_incomplete_amounts: true",
                "has_incomplete_amounts": True,
            }), 409

    cfg = current_app.config
    now = dt.now(cfg["HARVEST_TIMEZONE"])
    print_time = now.strftime("%Y-%m-%d %H:%M:%S")

    product_lines_for_render = []
    for line in ticket.product_lines:
        product_lines_for_render.append({
            "product_name": line.product_name,
            "rate_per_kg": line.rate_per_kg,
            "weight_kg": line.weight_kg,
            "amount_mxn": line.amount_mxn,
            "registration_type": line.registration_type,
            "sack_count": line.sack_count,
            "average_sack_weight_kg": line.average_sack_weight_kg,
        })

    ticket_bytes = render_ticket(
        business_name=cfg.get("TICKET_BUSINESS_NAME", "Sistema de Cosecha"),
        operational_date_str=op_date.isoformat(),
        slot_label=ticket.slot_label,
        worker_name=ticket.worker_name,
        worker_barcode=ticket.worker_barcode,
        worker_assignment_id=ticket.worker_assignment_id,
        product_lines=product_lines_for_render,
        total_weight_kg=ticket.total_weight_kg,
        total_amount_mxn=ticket.total_amount_mxn,
        print_time_str=print_time,
        has_incomplete_amounts=ticket.has_incomplete_amounts,
        footer_text=cfg.get("TICKET_FOOTER_TEXT", "Conserve este comprobante"),
        cpl=cfg.get("TICKET_CHARACTERS_PER_LINE", 48),
        encoding=cfg.get("TICKET_ENCODING", "cp850"),
        auto_cut=cfg.get("TICKET_AUTO_CUT", True),
    )

    try:
        print_raw(printer_name, ticket_bytes)
    except PrinterError as e:
        return jsonify({"error": "Error al imprimir ticket"}), 502

    return jsonify({"message": "Ticket impreso exitosamente"})
