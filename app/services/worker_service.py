from app.extensions import db
from app.models.worker import Worker


def search_workers(query=None):
    q = Worker.query
    if query:
        pattern = f"%{query}%"
        q = q.filter(
            db.or_(
                Worker.name.ilike(pattern),
                Worker.barcode.ilike(pattern),
            )
        )
    return q.order_by(Worker.name.asc()).all()


def get_worker_by_id(worker_id):
    return db.session.get(Worker, worker_id)


def create_worker(name, barcode):
    worker = Worker(name=name, barcode=barcode)
    db.session.add(worker)
    db.session.commit()
    return worker


def deactivate_worker(worker_id):
    worker = db.session.get(Worker, worker_id)
    if worker is None:
        return None
    worker.active = False
    db.session.commit()
    return worker


def activate_worker(worker_id):
    worker = db.session.get(Worker, worker_id)
    if worker is None:
        return None
    worker.active = True
    db.session.commit()
    return worker
