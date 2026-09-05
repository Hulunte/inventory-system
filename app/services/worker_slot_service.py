import re
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.worker import Worker
from app.models.worker_assignment import WorkerAssignment

BARCODE_PATTERN = re.compile(r"^TRB\d{6}$")
MAX_SLOT_NUMBER = 150


def slot_label(slot_number):
    return f"Trabajador {slot_number:03d}"


def validate_barcode(barcode):
    if not isinstance(barcode, str):
        return False
    return bool(BARCODE_PATTERN.match(barcode))


def validate_person_name(name):
    if not isinstance(name, str):
        raise ValueError("person_name must be a string")
    name = name.strip()
    if not name:
        raise ValueError("person_name is required")
    if len(name) > 150:
        raise ValueError("person_name must be at most 150 characters")
    return name


def serialize_worker_slot(worker, assignment=None):
    return {
        "id": worker.id,
        "slot_number": worker.slot_number,
        "slot_label": slot_label(worker.slot_number),
        "barcode": worker.barcode,
        "name": worker.name,
        "active": worker.active,
        "assignment_id": assignment.id if assignment else None,
        "person_name": assignment.person_name if assignment else None,
        "started_at": assignment.started_at.isoformat() if assignment else None,
    }


def serialize_worker_slot_full(worker, assignment=None):
    base = serialize_worker_slot(worker, assignment)
    base["created_at"] = worker.created_at.isoformat()
    return base


def search_worker_slots(query=None, include_inactive=False):
    q = Worker.query.order_by(Worker.slot_number.asc())

    if not include_inactive:
        q = q.filter(Worker.active.is_(True))

    if query:
        pattern = f"%{query}%"
        q = q.filter(
            db.or_(
                Worker.barcode.ilike(pattern),
                Worker.name.ilike(pattern),
                Worker.slot_number.cast(db.String).ilike(pattern),
            )
        )

    return q.all()


def get_worker_slot_by_id(worker_id):
    return db.session.get(Worker, worker_id)


def get_worker_slot_by_barcode(barcode):
    return Worker.query.filter_by(barcode=barcode).first()


def get_open_assignment(worker_id):
    return WorkerAssignment.query.filter_by(
        worker_id=worker_id, ended_at=None
    ).first()


def assign_person(worker_id, person_name):
    person_name = validate_person_name(person_name)

    worker = (
        db.session.query(Worker)
        .filter(Worker.id == worker_id)
        .with_for_update()
        .one_or_none()
    )
    if worker is None:
        raise ValueError("Worker not found")

    if not worker.active:
        raise ValueError("Cannot assign to an inactive slot")

    open_assignment = (
        WorkerAssignment.query
        .filter_by(worker_id=worker_id, ended_at=None)
        .with_for_update()
        .first()
    )

    now = datetime.now(timezone.utc)

    if open_assignment is not None:
        open_assignment.ended_at = now
        db.session.flush()

    new_assignment = WorkerAssignment(
        worker_id=worker_id,
        person_name=person_name,
        started_at=now,
    )
    db.session.add(new_assignment)

    worker.name = person_name

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise

    return new_assignment


def clean_all_assignments():
    now = datetime.now(timezone.utc)

    open_assignments = WorkerAssignment.query.filter_by(ended_at=None).all()

    count = len(open_assignments)

    for assignment in open_assignments:
        assignment.ended_at = now

    Worker.query.update({Worker.name: None})

    db.session.commit()

    return count


def deactivate_slot(worker_id):
    worker = db.session.get(Worker, worker_id)
    if worker is None:
        return None
    worker.active = False
    db.session.commit()
    return worker


def activate_slot(worker_id):
    worker = db.session.get(Worker, worker_id)
    if worker is None:
        return None
    worker.active = True
    db.session.commit()
    return worker
