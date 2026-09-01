import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, jsonify, session, request
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models.worker import Worker
from app.services.admin_service import (
    get_harvest_entries_for_admin,
    verify_admin_password,
    void_harvest_entry,
)
from app.services.worker_service import (
    activate_worker,
    create_worker,
    deactivate_worker,
    get_worker_by_id,
    search_workers,
)

admin_bp = Blueprint("admin", __name__)

ADMIN_MUTATING_METHODS = {"POST", "PATCH", "PUT", "DELETE"}


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"error": "Admin authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


def require_csrf(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ADMIN_MUTATING_METHODS:
            if request.path.startswith("/api/admin/"):
                token = request.headers.get("X-CSRF-Token")
                if not token or not secrets.compare_digest(token, session.get("csrf_token", "")):
                    return jsonify({"error": "CSRF token invalid"}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.before_request
def ensure_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)


@admin_bp.get("/api/admin/session")
def get_session():
    return jsonify({
        "authenticated": bool(session.get("admin")),
        "csrf_token": session.get("csrf_token", ""),
    })


@admin_bp.post("/api/admin/login")
@require_csrf
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    password = data.get("password", "")
    if not password:
        return jsonify({"error": "password is required"}), 400

    if not verify_admin_password(password):
        return jsonify({"error": "Invalid password"}), 401

    session.permanent = True
    session["admin"] = True
    session["csrf_token"] = secrets.token_hex(32)

    return jsonify({"message": "Login successful"})


@admin_bp.post("/api/admin/logout")
@require_admin
@require_csrf
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@admin_bp.get("/api/admin/workers")
@require_admin
def list_workers():
    query = request.args.get("q", "").strip() or None
    workers = search_workers(query)

    return jsonify(
        [
            {
                "id": w.id,
                "barcode": w.barcode,
                "name": w.name,
                "active": w.active,
                "created_at": w.created_at.isoformat(),
            }
            for w in workers
        ]
    )


@admin_bp.get("/api/admin/workers/<int:worker_id>")
@require_admin
def get_worker(worker_id):
    worker = get_worker_by_id(worker_id)

    if worker is None:
        return jsonify({"error": "Worker not found"}), 404

    return jsonify(
        {
            "id": worker.id,
            "barcode": worker.barcode,
            "name": worker.name,
            "active": worker.active,
            "created_at": worker.created_at.isoformat(),
        }
    )


@admin_bp.post("/api/admin/workers")
@require_admin
@require_csrf
def create():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    name = (data.get("name") or "").strip()
    barcode = (data.get("barcode") or "").strip()

    if not name:
        return jsonify({"error": "name is required"}), 400

    if not barcode:
        return jsonify({"error": "barcode is required"}), 400

    existing = Worker.query.filter_by(barcode=barcode).first()

    if existing:
        return jsonify({"error": "Barcode already exists"}), 409

    worker = create_worker(name=name, barcode=barcode)

    return (
        jsonify(
            {
                "id": worker.id,
                "barcode": worker.barcode,
                "name": worker.name,
                "active": worker.active,
                "created_at": worker.created_at.isoformat(),
            }
        ),
        201,
    )


@admin_bp.patch("/api/admin/workers/<int:worker_id>/deactivate")
@require_admin
@require_csrf
def deactivate(worker_id):
    worker = deactivate_worker(worker_id)

    if worker is None:
        return jsonify({"error": "Worker not found"}), 404

    return jsonify(
        {
            "id": worker.id,
            "barcode": worker.barcode,
            "name": worker.name,
            "active": worker.active,
        }
    )


@admin_bp.patch("/api/admin/workers/<int:worker_id>/activate")
@require_admin
@require_csrf
def activate(worker_id):
    worker = activate_worker(worker_id)

    if worker is None:
        return jsonify({"error": "Worker not found"}), 404

    return jsonify(
        {
            "id": worker.id,
            "barcode": worker.barcode,
            "name": worker.name,
            "active": worker.active,
        }
    )


@admin_bp.get("/api/admin/harvest-entries")
@require_admin
def list_harvest_entries():
    from flask import current_app
    from datetime import datetime as dt

    date_str = request.args.get("date")
    query_filter = request.args.get("q", "").strip() or None

    if date_str:
        try:
            operational_date = dt.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
    else:
        tz = current_app.config["HARVEST_TIMEZONE"]
        operational_date = dt.now(tz).date()

    entries = get_harvest_entries_for_admin(operational_date, query_filter)

    return jsonify({
        "date": operational_date.isoformat(),
        "entries": entries,
    })


@admin_bp.patch("/api/admin/harvest-entries/<int:entry_id>/void")
@require_admin
@require_csrf
def void_entry(entry_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    reason = data.get("reason", "")

    entry, status = void_harvest_entry(entry_id, reason)

    if status == "not_found":
        return jsonify({"error": "Harvest entry not found"}), 404

    if status == "already_voided":
        return jsonify({"error": "Harvest entry is already voided"}), 409

    if status == "empty_reason":
        return jsonify({"error": "reason is required"}), 400

    worker = entry.worker

    return jsonify({
        "id": entry.id,
        "worker": {
            "id": worker.id,
            "barcode": worker.barcode,
            "name": worker.name,
        },
        "weight_kg": str(entry.weight_kg),
        "created_at": entry.created_at.isoformat(),
        "voided": entry.voided,
        "voided_at": entry.voided_at.isoformat() if entry.voided_at else None,
        "void_reason": entry.void_reason,
    })
