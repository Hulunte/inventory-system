from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index, text

from app.extensions import db


class WorkerAssignment(db.Model):
    __tablename__ = "worker_assignments"
    __table_args__ = (
        CheckConstraint(
            "LENGTH(TRIM(person_name)) > 0",
            name="ck_worker_assignments_person_name_not_empty",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_worker_assignments_ended_at_gte_started_at",
        ),
        Index(
            "ux_worker_assignments_open_per_worker",
            "worker_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    worker_id = db.Column(
        db.Integer,
        db.ForeignKey("workers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    person_name = db.Column(db.String(150), nullable=False)

    started_at = db.Column(
        db.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    ended_at = db.Column(db.DateTime(timezone=True), nullable=True)

    worker = db.relationship("Worker", backref=db.backref(
        "assignments", lazy="dynamic", order_by="WorkerAssignment.started_at.desc()"
    ))

    def __repr__(self):
        status = "open" if self.ended_at is None else "closed"
        return f"<WorkerAssignment {self.person_name} slot={self.worker_id} {status}>"
