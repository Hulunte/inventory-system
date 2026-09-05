from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db


class Worker(db.Model):
    __tablename__ = "workers"
    __table_args__ = (
        CheckConstraint(
            "slot_number BETWEEN 1 AND 150",
            name="ck_workers_slot_number_range",
        ),
        CheckConstraint(
            "barcode ~ '^TRB[0-9]{6}$'",
            name="ck_workers_barcode_fixed_format",
        ),
        CheckConstraint(
            "barcode = 'TRB' || LPAD(slot_number::text, 6, '0')",
            name="ck_workers_barcode_matches_slot",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    slot_number = db.Column(db.Integer, unique=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<Worker {self.barcode} slot={self.slot_number}>"

    @property
    def slot_label(self):
        return f"Trabajador {self.slot_number:03d}"
