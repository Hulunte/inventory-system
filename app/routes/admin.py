import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, Response, jsonify, session, request
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models.worker import Worker
from app.services.admin_service import (
    get_harvest_entries_for_admin,
    verify_admin_password,
    void_harvest_entry,
)
from app.services.backup_service import create_backup, list_backups
from app.services.export_service import generate_credentials_export
from app.services.product_service import (
    DuplicateProductError,
    activate_product,
    create_product,
    deactivate_product,
    search_products,
    serialize_product,
    update_product,
)
from app.services.worker_slot_service import (
    activate_slot,
    assign_person,
    clean_all_assignments,
    deactivate_slot,
    get_worker_slot_by_id,
    search_worker_slots,
    serialize_worker_slot_full,
    validate_person_name,
)
from app.models.worker_assignment import WorkerAssignment

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


@admin_bp.get("/api/admin/worker-slots")
@require_admin
def list_worker_slots():
    query = request.args.get("q", "").strip() or None
    include_inactive = request.args.get("include_inactive", "").lower() == "true"
    workers = search_worker_slots(query, include_inactive=include_inactive)

    worker_ids = [w.id for w in workers]
    open_assignments = WorkerAssignment.query.filter(
        WorkerAssignment.worker_id.in_(worker_ids),
        WorkerAssignment.ended_at.is_(None),
    ).all()
    assignments_by_worker = {a.worker_id: a for a in open_assignments}

    result = []
    for w in workers:
        assignment = assignments_by_worker.get(w.id)
        result.append(serialize_worker_slot_full(w, assignment))

    return jsonify(result)


@admin_bp.patch("/api/admin/worker-slots/<int:worker_id>/assign")
@require_admin
@require_csrf
def assign_worker_slot(worker_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    KNOWN_FIELDS = {"person_name"}
    unknown = set(data.keys()) - KNOWN_FIELDS
    if unknown:
        return jsonify({"error": f"Unknown fields: {', '.join(sorted(unknown))}"}), 400

    person_name = data.get("person_name")
    if person_name is None:
        return jsonify({"error": "person_name is required"}), 400

    try:
        assignment = assign_person(worker_id, person_name)
    except ValueError as e:
        error_msg = str(e)
        if error_msg == "Worker not found":
            return jsonify({"error": error_msg}), 404
        if error_msg == "Cannot assign to an inactive slot":
            return jsonify({"error": error_msg}), 409
        return jsonify({"error": error_msg}), 400

    worker = get_worker_slot_by_id(worker_id)
    return jsonify(serialize_worker_slot_full(worker, assignment)), 200


@admin_bp.post("/api/admin/worker-slots/clean")
@require_admin
@require_csrf
def clean_worker_slots():
    count = clean_all_assignments()
    return jsonify({"message": f"Se limpiaron {count} asignaciones.", "count": count})


@admin_bp.patch("/api/admin/worker-slots/<int:worker_id>/activate")
@require_admin
@require_csrf
def activate_worker_slot(worker_id):
    worker = activate_slot(worker_id)
    if worker is None:
        return jsonify({"error": "Worker not found"}), 404
    assignment = WorkerAssignment.query.filter_by(
        worker_id=worker.id, ended_at=None
    ).first()
    return jsonify(serialize_worker_slot_full(worker, assignment))


@admin_bp.patch("/api/admin/worker-slots/<int:worker_id>/deactivate")
@require_admin
@require_csrf
def deactivate_worker_slot(worker_id):
    worker = deactivate_slot(worker_id)
    if worker is None:
        return jsonify({"error": "Worker not found"}), 404
    assignment = WorkerAssignment.query.filter_by(
        worker_id=worker.id, ended_at=None
    ).first()
    return jsonify(serialize_worker_slot_full(worker, assignment))


@admin_bp.get("/api/admin/worker-slots/export")
@require_admin
def export_worker_slots():
    xlsx_bytes = generate_credentials_export()
    filename = "credenciales_trabajadores.xlsx"

    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@admin_bp.get("/api/admin/products")
@require_admin
def list_products():
    query = request.args.get("q", "").strip() or None
    products = search_products(query)
    return jsonify([serialize_product(p) for p in products])


@admin_bp.post("/api/admin/products")
@require_admin
@require_csrf
def create_product_endpoint():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400
    if not data:
        return jsonify({"error": "Request body must not be empty"}), 400

    KNOWN_FIELDS = {"name", "rate_per_kg"}
    unknown = set(data.keys()) - KNOWN_FIELDS
    if unknown:
        return jsonify({"error": "Unknown fields: " + ", ".join(sorted(unknown))}), 400

    if "name" not in data:
        return jsonify({"error": "name is required"}), 400
    if "rate_per_kg" not in data:
        return jsonify({"error": "rate_per_kg is required"}), 400

    if data["name"] is None:
        return jsonify({"error": "name must not be null"}), 400
    if data["rate_per_kg"] is None:
        return jsonify({"error": "rate_per_kg must not be null"}), 400

    try:
        product = create_product(name=data["name"], rate_per_kg=data["rate_per_kg"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except DuplicateProductError:
        return jsonify({"error": "El producto ya existe."}), 409

    return jsonify(serialize_product(product)), 201


@admin_bp.patch("/api/admin/products/<int:product_id>")
@require_admin
@require_csrf
def update_product_endpoint(product_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400
    if not data:
        return jsonify({"error": "Request body must not be empty"}), 400

    KNOWN_FIELDS = {"name", "rate_per_kg"}
    unknown = set(data.keys()) - KNOWN_FIELDS
    if unknown:
        return jsonify({"error": "Unknown fields: " + ", ".join(sorted(unknown))}), 400

    if "name" not in data and "rate_per_kg" not in data:
        return jsonify({"error": "At least one field (name, rate_per_kg) is required"}), 400

    if "name" in data and data["name"] is None:
        return jsonify({"error": "name must not be null"}), 400
    if "rate_per_kg" in data and data["rate_per_kg"] is None:
        return jsonify({"error": "rate_per_kg must not be null"}), 400

    kwargs = {}
    if "name" in data:
        kwargs["name"] = data["name"]
    if "rate_per_kg" in data:
        kwargs["rate_per_kg"] = data["rate_per_kg"]

    try:
        product = update_product(product_id, **kwargs)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except DuplicateProductError:
        return jsonify({"error": "El producto ya existe."}), 409

    if product is None:
        return jsonify({"error": "Product not found"}), 404

    return jsonify(serialize_product(product)), 200


@admin_bp.patch("/api/admin/products/<int:product_id>/activate")
@require_admin
@require_csrf
def activate_product_endpoint(product_id):
    product = activate_product(product_id)
    if product is None:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(serialize_product(product)), 200


@admin_bp.patch("/api/admin/products/<int:product_id>/deactivate")
@require_admin
@require_csrf
def deactivate_product_endpoint(product_id):
    product = deactivate_product(product_id)
    if product is None:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(serialize_product(product)), 200


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

    worker_name = entry.worker_name_snapshot or worker.name or ""
    worker_barcode = entry.worker_barcode_snapshot or worker.barcode
    slot_number = entry.worker_slot_number_snapshot or worker.slot_number

    return jsonify({
        "id": entry.id,
        "worker": {
            "id": worker.id,
            "barcode": worker_barcode,
            "name": worker_name,
            "slot_number": slot_number,
            "slot_label": f"Trabajador {slot_number:03d}",
        },
        "weight_kg": str(entry.weight_kg),
        "created_at": entry.created_at.isoformat(),
        "voided": entry.voided,
        "voided_at": entry.voided_at.isoformat() if entry.voided_at else None,
        "void_reason": entry.void_reason,
    })


@admin_bp.get("/api/admin/backups")
@require_admin
def get_backups():
    data, error = list_backups()
    if error:
        return jsonify({"error": error}), 500
    return jsonify(data)


@admin_bp.post("/api/admin/backups")
@require_admin
@require_csrf
def create_backup_endpoint():
    info, error = create_backup()
    if error:
        if "no está configurado" in error:
            return jsonify({"error": error}), 400
        if "Ya hay un respaldo" in error:
            return jsonify({"error": error}), 409
        return jsonify({"error": error}), 500
    return jsonify({
        "message": "Respaldo creado exitosamente",
        "backup": info,
    }), 201
