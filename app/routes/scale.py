import secrets
import sys
from functools import wraps

from flask import Blueprint, jsonify, redirect, request, session, url_for

from app.services.scale_config import load_scale_config, validate_port_name
from app.services.scale_service import (
    ScaleConnectionError,
    ScaleUnavailableError,
    get_scale_service,
    is_available,
    list_ports,
)

scale_bp = Blueprint("scale", __name__)

ADMIN_MUTATING = {"POST", "PATCH", "PUT", "DELETE"}


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


@scale_bp.get("/api/scale/ports")
def api_list_ports():
    """List serial ports without opening them or requiring an admin session."""
    if not is_available():
        return jsonify({
            "ports": [],
            "available": False,
            "code": "pyserial_unavailable",
            "message": "PySerial no disponible",
        }), 503

    try:
        ports = list_ports(raise_errors=True)
    except Exception:
        return jsonify({
            "error": "No se pudo consultar la disponibilidad de puertos.",
            "code": "serial_port_enumeration_error",
        }), 500

    if ports:
        code = "scale_not_connected"
        message = "Hay puertos disponibles, pero no se ha conectado una báscula."
    else:
        code = "no_serial_ports"
        message = "No hay puertos disponibles"

    return jsonify({
        "ports": ports,
        "available": True,
        "code": code,
        "message": message,
    })


@scale_bp.get("/api/scale/status")
@_require_admin
def api_scale_status():
    """Get current scale connection status."""
    svc = get_scale_service()
    return jsonify(svc.get_status())


@scale_bp.post("/api/scale/connect")
@_require_admin
@_require_csrf
def api_scale_connect():
    """Connect to a serial scale."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    KNOWN_FIELDS = {"port", "baudrate", "bytesize", "parity", "stopbits", "timeout_seconds", "line_encoding", "profile"}
    unknown = set(data.keys()) - KNOWN_FIELDS
    if unknown:
        return jsonify({"error": f"Unknown fields: {', '.join(sorted(unknown))}"}), 400

    svc = get_scale_service()
    if svc.connected:
        return jsonify({"error": f"Ya conectado a {svc.port_name}. Desconecte primero."}), 409

    if not is_available():
        return jsonify({
            "error": "El componente serial no esta instalado.",
            "code": "pyserial_unavailable",
        }), 503

    port = (data.get("port") or "").strip()
    if not port:
        return jsonify({"error": "port is required"}), 400
    if not validate_port_name(port):
        return jsonify({"error": "Nombre de puerto invalido"}), 400

    import os
    os.environ["SCALE_PORT"] = port

    if "baudrate" in data:
        os.environ["SCALE_BAUDRATE"] = str(int(data["baudrate"]))
    if "bytesize" in data:
        os.environ["SCALE_BYTESIZE"] = str(int(data["bytesize"]))
    if "parity" in data:
        os.environ["SCALE_PARITY"] = str(data["parity"]).upper()
    if "stopbits" in data:
        os.environ["SCALE_STOPBITS"] = str(float(data["stopbits"]))
    if "timeout_seconds" in data:
        os.environ["SCALE_TIMEOUT_SECONDS"] = str(float(data["timeout_seconds"]))
    if "line_encoding" in data:
        os.environ["SCALE_LINE_ENCODING"] = str(data["line_encoding"])
    if "profile" in data:
        os.environ["SCALE_PROFILE"] = str(data["profile"])

    try:
        config = load_scale_config()
    except ValueError as e:
        return jsonify({"error": str(e), "code": "invalid_configuration"}), 400

    try:
        svc.connect(config)
    except ScaleUnavailableError as e:
        return jsonify({
            "error": str(e),
            "code": "pyserial_unavailable",
        }), 503
    except ScaleConnectionError as e:
        code = svc.get_status().get("code", "serial_read_error")
        return jsonify({"error": str(e), "code": code}), 422

    return jsonify(svc.get_status())


@scale_bp.post("/api/scale/disconnect")
@_require_admin
@_require_csrf
def api_scale_disconnect():
    """Disconnect from the serial scale."""
    svc = get_scale_service()
    if not svc.connected:
        return jsonify({"error": "No hay conexion activa"}), 409

    svc.disconnect()
    return jsonify(svc.get_status())


@scale_bp.post("/api/scale/test")
@_require_admin
@_require_csrf
def api_scale_test():
    """Test scale connection: send a read request and report the result."""
    svc = get_scale_service()
    if not svc.connected:
        return jsonify({"error": "No hay conexion activa. Conecte la bascula primero."}), 409

    reading = svc.last_reading
    if reading is None:
        return jsonify({
            "ok": False,
            "message": "Sin lectura disponible. Verifique que la bascula este enviando datos.",
            "status": svc.get_status(),
        })

    return jsonify({
        "ok": reading.ok,
        "message": "Lectura recibida" if reading.ok else f"Error: {reading.error}",
        "reading": reading.to_dict() if reading.ok else None,
        "error": reading.error,
        "status": svc.get_status(),
    })


@scale_bp.post("/api/scale/diagnostic")
@_require_admin
@_require_csrf
def api_scale_diagnostic():
    """Toggle diagnostic mode for raw line inspection."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    enabled = data.get("enabled")
    if not isinstance(enabled, bool):
        return jsonify({"error": "enabled must be a boolean"}), 400

    svc = get_scale_service()
    svc.set_diagnostic_mode(enabled)

    return jsonify({
        "diagnostic_mode": svc.diagnostic_mode,
        "raw_lines": svc.raw_lines if enabled else [],
    })
