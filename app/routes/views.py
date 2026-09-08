from datetime import datetime as dt
import os
import sys

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for, jsonify

from app.services.report_service import get_week_ranges

views_bp = Blueprint("views", __name__)


def _is_setup_needed():
    admin_hash = os.environ.get("ADMIN_PASSWORD_HASH", "")
    return not admin_hash or admin_hash == "replace-with-generated-password-hash"


def _get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _operational_today():
    """Return today's date in HARVEST_TIMEZONE as a date object."""
    tz = current_app.config["HARVEST_TIMEZONE"]
    return dt.now(tz).date()


@views_bp.before_request
def _check_setup_needed():
    if request.endpoint in ("views.setup_page", "views.setup_api"):
        return None
    if _is_setup_needed():
        return redirect(url_for("views.setup_page"))
    return None


@views_bp.get("/setup")
def setup_page():
    return render_template("setup.html")


@views_bp.post("/api/setup")
def setup_api():
    from werkzeug.security import check_password_hash, generate_password_hash

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    admin_password = data.get("admin_password") or ""

    if not admin_password or len(admin_password) < 8:
        return jsonify({"error": "La contrasena debe tener al menos 8 caracteres"}), 400

    app_port = data.get("app_port", "5000")
    try:
        port_int = int(app_port)
        if not (1 <= port_int <= 65535):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Puerto invalido"}), 400

    app_access = data.get("app_access", "local")
    host = "127.0.0.1" if app_access == "local" else "0.0.0.0"

    harvest_timezone = (data.get("harvest_timezone") or "America/Chihuahua").strip()
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        ZoneInfo(harvest_timezone)
    except (ZoneInfoNotFoundError, KeyError, ValueError):
        return jsonify({"error": "Zona horaria invalida"}), 400

    admin_password_hash = generate_password_hash(admin_password)
    if not check_password_hash(admin_password_hash, admin_password):
        return jsonify({"error": "No se pudo validar la contrasena generada"}), 500

    base_dir = _get_base_dir()
    env_path = os.path.join(base_dir, ".env")

    existing_env = {}
    if os.path.exists(env_path):
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        existing_env[key.strip()] = value.strip()
        except OSError:
            pass

    db_url = existing_env.get("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    if not db_url:
        return jsonify({"error": "DATABASE_URL no esta configurado. Contacte al administrador."}), 500

    secret_key = existing_env.get("SECRET_KEY") or os.environ.get("SECRET_KEY", "")
    if not secret_key or len(secret_key) < 32:
        import secrets
        secret_key = secrets.token_hex(32)

    smtp_host = (data.get("smtp_host") or "").strip()
    smtp_user = (data.get("smtp_username") or "").strip()
    smtp_pass = data.get("smtp_app_password") or ""
    smtp_requested = bool(smtp_host or smtp_user or smtp_pass)

    smtp_config = {}
    if smtp_requested:
        for field, value in (
            ("MAIL_SMTP_HOST", smtp_host),
            ("MAIL_SMTP_USERNAME", smtp_user),
            ("MAIL_SMTP_APP_PASSWORD", smtp_pass),
        ):
            if not value:
                return jsonify({"error": f"Falta la variable {field}"}), 400
        try:
            smtp_port = int(data.get("smtp_port", "587"))
            if not (1 <= smtp_port <= 65535):
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "MAIL_SMTP_PORT debe estar entre 1 y 65535"}), 400

        smtp_config = {
            "MAIL_SMTP_HOST": smtp_host,
            "MAIL_SMTP_PORT": str(smtp_port),
            "MAIL_SMTP_USERNAME": smtp_user,
            "MAIL_SMTP_APP_PASSWORD": smtp_pass,
            "MAIL_FROM_ADDRESS": smtp_user,
            "MAIL_FROM_NAME": "Sistema de Cosecha",
            "MAIL_USE_TLS": "true",
            "MAIL_TIMEOUT_SECONDS": "30",
        }

    env_lines = [
        f"SECRET_KEY={secret_key}",
        f"ADMIN_PASSWORD_HASH={admin_password_hash}",
        f"HARVEST_TIMEZONE={harvest_timezone}",
        f"APP_HOST={host}",
        f"APP_PORT={port_int}",
        "SESSION_COOKIE_SECURE=false",
        f"DATABASE_URL={db_url}",
    ]

    if smtp_config:
        env_lines.extend(f"{key}={value}" for key, value in smtp_config.items())

    preserved_keys = ("PG_DUMP_PATH", "BACKUP_DIR", "TICKET_BUSINESS_NAME", "TICKET_FOOTER_TEXT",
                "TICKET_PAPER_WIDTH_MM", "TICKET_CHARACTERS_PER_LINE", "TICKET_PRINTER_NAME",
                "TICKET_ENCODING", "TICKET_AUTO_CUT", "SCALE_PORT", "SCALE_BAUDRATE",
                "SCALE_BYTESIZE", "SCALE_PARITY", "SCALE_STOPBITS", "SCALE_TIMEOUT_SECONDS",
                "SCALE_LINE_ENCODING", "SCALE_PROFILE", "SCALE_MIN_WEIGHT_KG", "SCALE_MAX_WEIGHT_KG",
                "MAIL_SMTP_HOST", "MAIL_SMTP_PORT", "MAIL_SMTP_USERNAME",
                "MAIL_SMTP_APP_PASSWORD", "MAIL_FROM_ADDRESS", "MAIL_FROM_NAME",
                "MAIL_USE_TLS", "MAIL_TIMEOUT_SECONDS")
    for key in preserved_keys:
        if key in smtp_config:
            continue
        if key in existing_env:
            env_lines.append(f"{key}={existing_env[key]}")

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(env_lines) + "\n")
    except OSError as e:
        return jsonify({"error": f"No se pudo guardar la configuracion: {e}"}), 500

    os.environ["ADMIN_PASSWORD_HASH"] = admin_password_hash
    os.environ["SECRET_KEY"] = secret_key
    current_app.config["ADMIN_PASSWORD_HASH"] = admin_password_hash
    current_app.config["SECRET_KEY"] = secret_key
    for key, value in smtp_config.items():
        os.environ[key] = value
        if key in ("MAIL_SMTP_PORT", "MAIL_TIMEOUT_SECONDS"):
            current_app.config[key] = int(value)
        else:
            current_app.config[key] = value

    return jsonify({"message": "Configuracion guardada correctamente.", "redirect": "/admin/login"}), 200


@views_bp.get("/")
def reception_page():
    return render_template("reception.html")


@views_bp.get("/admin/login")
def admin_login_page():
    if session.get("admin"):
        return redirect(url_for("views.admin_page"))
    return render_template("admin_login.html")


@views_bp.get("/admin")
def admin_page():
    if not session.get("admin"):
        return redirect(url_for("views.admin_login_page"))
    return render_template("admin.html", operational_today=_operational_today().isoformat())


@views_bp.get("/admin/products")
def products_page():
    if not session.get("admin"):
        return redirect(url_for("views.admin_login_page"))
    return render_template("products.html")


@views_bp.get("/history")
def history_page():
    if not session.get("admin"):
        return redirect(url_for("views.admin_login_page"))
    return render_template("history.html", operational_today=_operational_today().isoformat())


@views_bp.get("/reports")
def reports_page():
    if not session.get("admin"):
        return redirect(url_for("views.admin_login_page"))
    today = _operational_today()
    (monday_current, sunday_current), (monday_previous, sunday_previous) = get_week_ranges(today)

    return render_template(
        "reports.html",
        is_admin=bool(session.get("admin")),
        csrf_token=session.get("csrf_token", ""),
        operational_today=today.isoformat(),
        current_week_start=monday_current.isoformat(),
        current_week_end=sunday_current.isoformat(),
        previous_week_start=monday_previous.isoformat(),
        previous_week_end=sunday_previous.isoformat(),
    )
